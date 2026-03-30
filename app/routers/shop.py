import uuid
import app.schemas as schemas

from fastapi import APIRouter, Request, Depends, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.base import get_session
from app.limiter import limiter
from app.services import Shop
from app.utils.deps import verify_session

router = APIRouter()

@router.get("/shop", summary="Получить информацию о магазине", response_model=schemas.ShopResponse,
            responses={404: {"model": schemas.ErrorMessage}, 429: {"model": schemas.ErrorMessage}})
@limiter.limit("60/minute")
async def get_shop(request: Request, seller_id: uuid.UUID = Depends(verify_session), session: AsyncSession = Depends(get_session)):
    return await Shop.get_shop(seller_id, session)

@router.post("/shop", summary="Создать магазин", response_model=schemas.Response,
             responses={400: {"model": schemas.ErrorMessage}, 500: {"model": schemas.ErrorMessage}, 429: {"model": schemas.ErrorMessage}})
@limiter.limit("3/minute")
async def create_shop(request: Request, data: schemas.CreateShop, seller_id: uuid.UUID = Depends(verify_session), session: AsyncSession = Depends(get_session)):
    return await Shop.create_shop(data, seller_id, session)

@router.patch("/shop", summary="Обновить магазин", response_model=schemas.ShopResponse,
              responses={400: {"model": schemas.ErrorMessage}, 404: {"model": schemas.ErrorMessage}, 500: {"model": schemas.ErrorMessage}, 429: {"model": schemas.ErrorMessage}})
@limiter.limit("10/minute")
async def update_shop(request: Request, data: schemas.UpdateShop, seller_id: uuid.UUID = Depends(verify_session), session: AsyncSession = Depends(get_session)):
    return await Shop.update_shop(data, seller_id, session)

@router.post("/shop/domain", summary="Подключить домен", response_model=schemas.ShopResponse,
             responses={400: {"model": schemas.ErrorMessage}, 404: {"model": schemas.ErrorMessage}, 500: {"model": schemas.ErrorMessage}, 429: {"model": schemas.ErrorMessage}})
@limiter.limit("3/minute")
async def connect_subdomain(request: Request, data: schemas.ConnectDomain, seller_id: uuid.UUID = Depends(verify_session), session: AsyncSession = Depends(get_session)):
    return await Shop.connect_domain(data, seller_id, session)

@router.post("/shop/logo", summary="Загрузить логотип магазина", response_model=schemas.ShopResponse,
             responses={400: {"model": schemas.ErrorMessage}, 500: {"model": schemas.ErrorMessage}, 429: {"model": schemas.ErrorMessage}})
@limiter.limit("10/minute")
async def upload_logo(request: Request, file: UploadFile = File(...), seller_id: uuid.UUID = Depends(verify_session), session: AsyncSession = Depends(get_session)):
    return await Shop.upload_logo(file, seller_id, session)