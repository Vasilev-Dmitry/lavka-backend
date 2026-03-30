import uuid
import app.schemas as schemas

from fastapi import APIRouter, Request, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.base import get_session
from app.limiter import limiter
from app.services import Showcase

router = APIRouter()

@router.get("/showcase/{domain}", summary="Получить информацию о магазине", response_model=schemas.ShowcaseResponse,
            responses={404: {"model": schemas.ErrorMessage}, 403: {"model": schemas.ErrorMessage}, 429: {"model": schemas.ErrorMessage}})
@limiter.limit("30/minute")
async def get_showcase(request: Request, domain: str, session: AsyncSession = Depends(get_session)):
    return await Showcase.get_showcase(domain, session)

@router.get("/showcase/{domain}/products", summary="Получить список товаров", response_model=list[schemas.ShowcaseProduct],
            responses={404: {"model": schemas.ErrorMessage}, 403: {"model": schemas.ErrorMessage}, 429: {"model": schemas.ErrorMessage}})
@limiter.limit("30/minute")
async def get_products(request: Request, domain: str, session: AsyncSession = Depends(get_session)):
    return await Showcase.get_products(domain, session)

@router.get("/showcase/{domain}/products/{product_id}", summary="Получить товар", response_model=schemas.ShowcaseProduct,
            responses={404: {"model": schemas.ErrorMessage}, 403: {"model": schemas.ErrorMessage}, 429: {"model": schemas.ErrorMessage}})
@limiter.limit("30/minute")
async def get_product(request: Request, domain: str, product_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    return await Showcase.get_product(domain, product_id, session)