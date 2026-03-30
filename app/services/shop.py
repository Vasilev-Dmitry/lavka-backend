import uuid

from fastapi import HTTPException, status, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy import update, select
from sentry_sdk import logger as sentry_logger

from app import schemas
from app.database.cache import redis
from app.database.models import Shop as ShopModel
from app.schemas import Response
from app.utils.validators import clean_domain
from app.constants import RESERVED_SUBDOMAINS
from app.utils.s3 import upload_image, delete_image

class Shop:
    CACHE_TTL = 600
    ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
    MAX_SIZE = 5 * 1024 * 1024

    @staticmethod
    def _cache_key(seller_id: uuid.UUID) -> str:
        return f"shop:{seller_id}"

    @staticmethod
    async def _get_shop(session, stmt, seller_id: uuid.UUID):
        result = await session.execute(stmt)
        shop = result.scalar_one_or_none()

        if not shop:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Shop not found")

        await session.commit()
        shop_data = schemas.ShopResponse.model_validate(shop)
        await redis.set(Shop._cache_key(seller_id), shop_data.model_dump_json(), ex=Shop.CACHE_TTL)
        return shop_data


    @staticmethod
    async def get_shop(seller_id: uuid.UUID, session: AsyncSession) -> schemas.ShopResponse:
        if cached := await redis.get(Shop._cache_key(seller_id)):
            return schemas.ShopResponse.model_validate_json(cached)

        try:
            result = await session.execute(
                select(ShopModel).where(ShopModel.seller_id == seller_id)
            )
            shop = result.scalar_one_or_none()
            if not shop:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "Shop not found")

            shop_data = schemas.ShopResponse.model_validate(shop)
            await redis.set(Shop._cache_key(seller_id), shop_data.model_dump_json(), ex=Shop.CACHE_TTL)
            return shop_data
        except HTTPException:
            raise
        except Exception as e:
            sentry_logger.error("Failed to get shop", attributes={"error": str(e), "seller_id": str(seller_id)})
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Something went wrong")

    @staticmethod
    async def create_shop(data: schemas.CreateShop, seller_id: uuid.UUID, session: AsyncSession) -> schemas.Response:
        new_shop = ShopModel(seller_id=seller_id, **data.model_dump())
        session.add(new_shop)

        try:
            await session.commit()
            await session.refresh(new_shop)
        except IntegrityError:
            await session.rollback()
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Shop already exists or data conflict")
        except Exception as e:
            await session.rollback()
            sentry_logger.error("Failed to create shop", attributes={"error": str(e), "seller_id": str(seller_id)})
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Something went wrong")

        shop_data = schemas.ShopResponse.model_validate(new_shop)
        await redis.set(Shop._cache_key(seller_id), shop_data.model_dump_json(), ex=Shop.CACHE_TTL)
        return Response(success=True, message="Shop created successfully")

    @staticmethod
    async def update_shop(data: schemas.UpdateShop, seller_id: uuid.UUID, session: AsyncSession) -> schemas.ShopResponse:
        update_data = data.model_dump(exclude_none=True)
        if not update_data:
            return await Shop.get_shop(seller_id, session)

        try:
            stmt = (
                update(ShopModel)
                .where(ShopModel.seller_id == seller_id)
                .values(**update_data)
                .returning(ShopModel)
            )
            return await Shop._get_shop(session, stmt, seller_id)

        except HTTPException:
            raise
        except IntegrityError:
            await session.rollback()
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Conflict: data already taken")
        except Exception as e:
            await session.rollback()
            sentry_logger.error("Failed to update shop", attributes={"error": str(e), "seller_id": str(seller_id)})
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Something went wrong")

    @staticmethod
    async def connect_domain(data: schemas.ConnectDomain, seller_id: uuid.UUID, session: AsyncSession) -> schemas.ShopResponse:
        domain = clean_domain(data.domain)

        if domain in RESERVED_SUBDOMAINS:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "This subdomain is reserved")

        try:
            stmt = (
                update(ShopModel)
                .where(ShopModel.seller_id == seller_id)
                .values(domain=domain)
                .returning(ShopModel)
            )
            return await Shop._get_shop(session, stmt, seller_id)

        except HTTPException:
            raise
        except IntegrityError:
            await session.rollback()
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "This subdomain is already taken")
        except Exception as e:
            await session.rollback()
            sentry_logger.error("Failed to connect domain", attributes={"error": str(e), "seller_id": str(seller_id), "subdomain": domain})
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Something went wrong")

    @staticmethod
    async def upload_logo(file: UploadFile, seller_id: uuid.UUID, session: AsyncSession) -> schemas.ShopResponse:
        if file.content_type not in Shop.ALLOWED_TYPES:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid file type. Allowed: JPEG, PNG, WEBP")

        file_bytes = await file.read()
        if len(file_bytes) > Shop.MAX_SIZE:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "File too large. Max 5MB")

        try:
            cached = await redis.get(Shop._cache_key(seller_id))
            if cached:
                old_shop = schemas.ShopResponse.model_validate_json(cached)
                if old_shop.logo:
                    await delete_image(old_shop.logo)
            else:
                result = await session.execute(
                    select(ShopModel.logo).where(ShopModel.seller_id == seller_id)
                )
                old_logo = result.scalar_one_or_none()
                if old_logo:
                    await delete_image(old_logo)

            logo_url = await upload_image(file_bytes, folder=f"logos/{seller_id}")

            stmt = (
                update(ShopModel)
                .where(ShopModel.seller_id == seller_id)
                .values(logo=logo_url)
                .returning(ShopModel)
            )
            return await Shop._get_shop(session, stmt, seller_id)

        except HTTPException:
            raise
        except Exception as e:
            await session.rollback()
            sentry_logger.error("Failed to upload logo", attributes={"error": str(e), "seller_id": str(seller_id)})
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Something went wrong")
