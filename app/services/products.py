import uuid
import json

from fastapi import HTTPException, status, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select, func, delete, update
from sentry_sdk import logger as sentry_logger

from app import schemas
from app.database.cache import redis
from app.database.models import Product as ProductModel, Shop as ShopModel, Seller as SellerModel
from app.schemas import Response
from app.constants import PLAN_LIMITS
from app.utils.s3 import upload_image, delete_image as delete_image_from_s3

class Products:
    CACHE_TTL = 600

    @staticmethod
    def _cache_key(seller_id: uuid.UUID) -> str:
        return f"products:{seller_id}"

    @staticmethod
    def _seller_cache_key(seller_id: uuid.UUID) -> str:
        return f"seller:{seller_id}"

    @staticmethod
    async def _get_shop(seller_id: uuid.UUID, session: AsyncSession) -> ShopModel:
        result = await session.execute(
            select(ShopModel).where(ShopModel.seller_id == seller_id)
        )
        shop = result.scalar_one_or_none()
        if not shop:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Shop not found")
        return shop

    @staticmethod
    async def _invalidate_cache(seller_id: uuid.UUID, domain: str) -> None:
        await redis.delete(Products._cache_key(seller_id))
        await redis.delete(f"showcase:products:{domain}")

    @staticmethod
    async def _is_subscribed(seller_id: uuid.UUID, session: AsyncSession) -> bool:
        cached = await redis.get(Products._seller_cache_key(seller_id))
        if cached:
            seller = schemas.SellerResponse.model_validate_json(cached)
            return seller.is_subscribed

        result = await session.execute(
            select(SellerModel.is_subscribed).where(SellerModel.id == seller_id)
        )
        return result.scalar_one_or_none() or False

    @staticmethod
    async def _get_product_count(shop_id: uuid.UUID, session: AsyncSession) -> int:
        result = await session.execute(
            select(func.count()).where(ProductModel.shop_id == shop_id)
        )
        return result.scalar_one()

    @staticmethod
    async def get_products(seller_id: uuid.UUID, session: AsyncSession) -> list[schemas.ProductResponse]:
        try:
            if cached := await redis.get(Products._cache_key(seller_id)):
                try:
                    return [schemas.ProductResponse.model_validate(item) for item in json.loads(cached)]
                except Exception:
                    await redis.delete(Products._cache_key(seller_id))

            shop = await Products._get_shop(seller_id, session)
            result = await session.execute(
                select(ProductModel)
                .where(ProductModel.shop_id == shop.id)
                .order_by(ProductModel.created_at.desc())
            )
            products = result.scalars().all()
            products_data = [schemas.ProductResponse.model_validate(p) for p in products]

            await redis.set(
                Products._cache_key(seller_id),
                json.dumps([p.model_dump(mode="json") for p in products_data]),
                ex=Products.CACHE_TTL,
            )
            return products_data

        except HTTPException:
            raise
        except Exception as e:
            sentry_logger.error("Failed to get products", attributes={"error": str(e), "seller_id": str(seller_id)})
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Something went wrong")

    @staticmethod
    async def create_product(data: schemas.CreateProduct, seller_id: uuid.UUID, session: AsyncSession) -> schemas.ProductResponse:
        try:
            shop = await Products._get_shop(seller_id, session)

            is_subscribed = await Products._is_subscribed(seller_id, session)
            limit = PLAN_LIMITS["business"] if is_subscribed else PLAN_LIMITS["free"]
            count = await Products._get_product_count(shop.id, session)

            if count >= limit:
                raise HTTPException(status.HTTP_403_FORBIDDEN, f"Product limit reached ({limit})")

            new_product = ProductModel(shop_id=shop.id, **data.model_dump(exclude_none=True))
            session.add(new_product)
            await session.commit()
            await session.refresh(new_product)

            await Products._invalidate_cache(seller_id, shop.domain)

            return schemas.ProductResponse.model_validate(new_product)

        except HTTPException:
            raise
        except IntegrityError:
            await session.rollback()
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Data conflict")
        except Exception as e:
            await session.rollback()
            sentry_logger.error("Failed to create product", attributes={"error": str(e), "seller_id": str(seller_id)})
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Something went wrong")

    @staticmethod
    async def update_product(product_id: uuid.UUID, data: schemas.UpdateProduct, seller_id: uuid.UUID, session: AsyncSession) -> schemas.ProductResponse:
        update_data = data.model_dump(exclude_none=True)
        if not update_data:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "No fields to update")

        try:
            shop = await Products._get_shop(seller_id, session)

            stmt = (
                update(ProductModel)
                .where(ProductModel.id == product_id, ProductModel.shop_id == shop.id)
                .values(**update_data)
                .returning(ProductModel)
            )
            result = await session.execute(stmt)
            product = result.scalar_one_or_none()

            if not product:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")

            await session.commit()
            await Products._invalidate_cache(seller_id, shop.domain)

            return schemas.ProductResponse.model_validate(product)

        except HTTPException:
            raise
        except IntegrityError:
            await session.rollback()
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Data conflict")
        except Exception as e:
            await session.rollback()
            sentry_logger.error("Failed to update product", attributes={"error": str(e), "seller_id": str(seller_id)})
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Something went wrong")

    @staticmethod
    async def delete_product(product_id: uuid.UUID, seller_id: uuid.UUID, session: AsyncSession) -> schemas.Response:
        try:
            shop = await Products._get_shop(seller_id, session)

            stmt = (
                delete(ProductModel)
                .where(ProductModel.id == product_id, ProductModel.shop_id == shop.id)
                .returning(ProductModel.id)
            )
            result = await session.execute(stmt)
            deleted = result.scalar_one_or_none()

            if not deleted:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")

            await session.commit()
            await Products._invalidate_cache(seller_id, shop.domain)

            return Response(success=True, message="Product deleted successfully")

        except HTTPException:
            raise
        except Exception as e:
            await session.rollback()
            sentry_logger.error("Failed to delete product", attributes={"error": str(e), "seller_id": str(seller_id)})
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Something went wrong")

    @staticmethod
    async def upload_image(product_id: uuid.UUID, file: UploadFile, seller_id: uuid.UUID, session: AsyncSession) -> schemas.ProductResponse:
        if file.content_type not in {"image/jpeg", "image/png", "image/webp"}:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid file type. Allowed: JPEG, PNG, WEBP")

        file_bytes = await file.read()
        if len(file_bytes) > 5 * 1024 * 1024:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "File too large. Max 5MB")

        try:
            shop = await Products._get_shop(seller_id, session)

            result = await session.execute(
                select(ProductModel).where(ProductModel.id == product_id, ProductModel.shop_id == shop.id)
            )
            product = result.scalar_one_or_none()
            if not product:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")

            images = product.images or []
            if len(images) >= 5:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "Maximum 5 images per product")

            image_url = await upload_image(file_bytes, folder=f"products/{product_id}")
            images.append(image_url)

            stmt = (
                update(ProductModel)
                .where(ProductModel.id == product_id, ProductModel.shop_id == shop.id)
                .values(images=images)
                .returning(ProductModel)
            )
            result = await session.execute(stmt)
            updated = result.scalar_one()
            await session.commit()
            await Products._invalidate_cache(seller_id, shop.domain)

            return schemas.ProductResponse.model_validate(updated)

        except HTTPException:
            raise
        except Exception as e:
            await session.rollback()
            sentry_logger.error("Failed to upload product image",
                                attributes={"error": str(e), "product_id": str(product_id)})
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Something went wrong")

    @staticmethod
    async def delete_image(product_id: uuid.UUID, image_index: int, seller_id: uuid.UUID,
                           session: AsyncSession) -> schemas.ProductResponse:
        try:
            shop = await Products._get_shop(seller_id, session)

            result = await session.execute(
                select(ProductModel).where(ProductModel.id == product_id, ProductModel.shop_id == shop.id)
            )
            product = result.scalar_one_or_none()
            if not product:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")

            images = product.images or []
            if image_index < 0 or image_index >= len(images):
                raise HTTPException(status.HTTP_400_BAD_REQUEST,
                                    f"Invalid image index. Product has {len(images)} images")

            url_to_delete = images.pop(image_index)
            await delete_image_from_s3(url_to_delete)

            stmt = (
                update(ProductModel)
                .where(ProductModel.id == product_id, ProductModel.shop_id == shop.id)
                .values(images=images)
                .returning(ProductModel)
            )
            result = await session.execute(stmt)
            updated = result.scalar_one()
            await session.commit()
            await Products._invalidate_cache(seller_id, shop.domain)

            return schemas.ProductResponse.model_validate(updated)

        except HTTPException:
            raise
        except Exception as e:
            await session.rollback()
            sentry_logger.error("Failed to delete product image",
                                attributes={"error": str(e), "product_id": str(product_id)})
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Something went wrong")
