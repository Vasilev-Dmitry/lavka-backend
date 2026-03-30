import uuid
import app.schemas as schemas

from fastapi import APIRouter, Request, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.base import get_session
from app.services import Profile
from app.utils.deps import verify_session
from app.limiter import limiter

router = APIRouter()

@router.get("/profile", summary="Получить информацию о профиле", response_model=schemas.SellerResponse,
            responses={404: {"model": schemas.ErrorMessage}, 429: {"model": schemas.ErrorMessage}})
@limiter.limit("60/minute")
async def get_profile(request: Request, seller_id: uuid.UUID = Depends(verify_session), session: AsyncSession = Depends(get_session)):
    return await Profile.get_profile(seller_id, session)