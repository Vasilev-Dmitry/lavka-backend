import uuid
import json

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sentry_sdk import logger as sentry_logger
from app import schemas
from app.database.cache import redis
from app.database.models import Shop as ShopModel, Seller as SellerModel, Product as ProductModel


class Showcase:
    SHOP_CACHE_TTL = 600
    PRODUCTS_CACHE_TTL = 600

    @staticmethod
    def _shop_cache_key(domain: str) -> str:
        return f"showcase:shop:{domain}"

    @staticmethod
    def _products_cache_key(domain: str) -> str:
        return f"showcase:products:{domain}"

    @staticmethod
    async def _get_shop_by_domain(domain: str, session: AsyncSession) -> ShopModel:
        try:
            result = await session.execute(
                select(ShopModel, SellerModel.is_active)
                .join(SellerModel, ShopModel.seller_id == SellerModel.id)
                .where(ShopModel.domain == domain)
            )
            row = result.one_or_none()

            if not row:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "Shop not found")

            shop, is_active = row
            if not is_active:
                raise HTTPException(status.HTTP_403_FORBIDDEN, "This shop is unavailable")

            return shop

        except HTTPException:
            raise
        except Exception as e:
            sentry_logger.error("Failed to get shop by domain", attributes={"error": str(e), "domain": domain})
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Something went wrong")

    @staticmethod
    async def get_showcase(domain: str, session: AsyncSession) -> schemas.ShowcaseResponse:
        try:
            if cached := await redis.get(Showcase._shop_cache_key(domain)):
                try:
                    return schemas.ShowcaseResponse.model_validate_json(cached)
                except Exception:
                    await redis.delete(Showcase._shop_cache_key(domain))

            shop = await Showcase._get_shop_by_domain(domain, session)
            shop_data = schemas.ShowcaseResponse.model_validate(shop)
            await redis.set(Showcase._shop_cache_key(domain), shop_data.model_dump_json(), ex=Showcase.SHOP_CACHE_TTL)
            return shop_data

        except HTTPException:
            raise
        except Exception as e:
            sentry_logger.error("Failed to get showcase", attributes={"error": str(e), "domain": domain})
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Something went wrong")

    @staticmethod
    async def get_products(domain: str, session: AsyncSession) -> list[schemas.ShowcaseProduct]:
        try:
            if cached := await redis.get(Showcase._products_cache_key(domain)):
                try:
                    return [schemas.ShowcaseProduct.model_validate_json(item) for item in json.loads(cached)]
                except Exception:
                    await redis.delete(Showcase._products_cache_key(domain))

            shop = await Showcase._get_shop_by_domain(domain, session)

            result = await session.execute(
                select(ProductModel)
                .where(ProductModel.shop_id == shop.id)
                .order_by(ProductModel.created_at.desc())
            )
            products = result.scalars().all()
            products_data = [schemas.ShowcaseProduct.model_validate(p) for p in products]

            await redis.set(
                Showcase._products_cache_key(domain),
                json.dumps([p.model_dump_json() for p in products_data]),
                ex=Showcase.PRODUCTS_CACHE_TTL,
            )
            return products_data

        except HTTPException:
            raise
        except Exception as e:
            sentry_logger.error("Failed to get showcase products", attributes={"error": str(e), "domain": domain})
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Something went wrong")

    @staticmethod
    async def get_product(domain: str, product_id: uuid.UUID, session: AsyncSession) -> schemas.ShowcaseProduct:
        try:
            if cached := await redis.get(Showcase._products_cache_key(domain)):
                try:
                    products = [schemas.ShowcaseProduct.model_validate_json(item) for item in json.loads(cached)]
                    product = next((p for p in products if p.id == product_id), None)
                    if product:
                        return product
                except Exception:
                    await redis.delete(Showcase._products_cache_key(domain))

            # Fallback в БД
            shop = await Showcase._get_shop_by_domain(domain, session)

            result = await session.execute(
                select(ProductModel)
                .where(ProductModel.id == product_id, ProductModel.shop_id == shop.id)
            )
            product = result.scalar_one_or_none()

            if not product:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")

            return schemas.ShowcaseProduct.model_validate(product)

        except HTTPException:
            raise
        except Exception as e:
            sentry_logger.error("Failed to get showcase product", attributes={"error": str(e), "domain": domain, "product_id": str(product_id)})
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Something went wrong")