import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
from app.database.models import Seller
from app.database.cache import redis
from app.schemas import SellerResponse

class Profile:
    @staticmethod
    async def get_profile(seller_id: uuid.UUID, session: AsyncSession) -> SellerResponse:
        data_by_redis = await redis.get(f"seller:{seller_id}")
        if data_by_redis:
            return SellerResponse.model_validate_json(data_by_redis)

        seller = await session.get(Seller, seller_id)
        if not seller:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Seller not found")

        seller_data = SellerResponse.model_validate(seller)
        await redis.set(f"seller:{seller_id}", seller_data.model_dump_json(), ex=600)

        return seller_data