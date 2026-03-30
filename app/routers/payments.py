import uuid
import app.schemas as schemas

from fastapi import APIRouter, Request, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.base import get_session
from app.limiter import limiter
from app.services import Payments
from app.utils.deps import verify_session

router = APIRouter()

@router.post("/create", summary="Создать платёж", response_model=schemas.InvoiceCreated,
             responses={400: {"model": schemas.ErrorMessage}, 404: {"model": schemas.ErrorMessage}, 500: {"model": schemas.ErrorMessage}, 503: {"model": schemas.ErrorMessage}, 429: {"model": schemas.ErrorMessage}})
@limiter.limit("5/minute")
async def create_invoice(request: Request, seller_id: uuid.UUID = Depends(verify_session), session: AsyncSession = Depends(get_session)):
    return await Payments.create(request, seller_id, session)

@router.post("/webhook", summary="Вебхук от CryptoCloud",
             responses={401: {"model": schemas.ErrorMessage}, 404: {"model": schemas.ErrorMessage}, 500: {"model": schemas.ErrorMessage}})
async def webhook(request: Request, session: AsyncSession = Depends(get_session)):
    return await Payments.webhook(request, session)