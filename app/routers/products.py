import uuid
import app.schemas as schemas

from fastapi import APIRouter, Depends, Request, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.base import get_session
from app.utils.deps import verify_session
from app.services import Products
from app.limiter import limiter

router = APIRouter()

@router.get("/me", summary="Получить список товаров", response_model=list[schemas.ProductResponse],
            responses={500: {"model": schemas.ErrorMessage}, 429: {"model": schemas.ErrorMessage}})
@limiter.limit("30/minute")
async def get_products(request: Request, seller_id: uuid.UUID = Depends(verify_session), session: AsyncSession = Depends(get_session)):
    return await Products.get_products(seller_id, session)

@router.post("/me", summary="Добавить товар", response_model=schemas.ProductResponse,
             responses={400: {"model": schemas.ErrorMessage}, 403: {"model": schemas.ErrorMessage}, 500: {"model": schemas.ErrorMessage}, 429: {"model": schemas.ErrorMessage}})
@limiter.limit("10/minute")
async def create_product(request: Request, data: schemas.CreateProduct, seller_id: uuid.UUID = Depends(verify_session), session: AsyncSession = Depends(get_session)):
    return await Products.create_product(data, seller_id, session)

@router.patch("/me/{product_id}", summary="Редактировать", response_model=schemas.ProductResponse,
              responses={400: {"model": schemas.ErrorMessage}, 404: {"model": schemas.ErrorMessage}, 500: {"model": schemas.ErrorMessage}, 429: {"model": schemas.ErrorMessage}})
@limiter.limit("10/minute")
async def update_product(request: Request, product_id: uuid.UUID, data: schemas.UpdateProduct, seller_id: uuid.UUID = Depends(verify_session), session: AsyncSession = Depends(get_session)):
    return await Products.update_product(product_id, data, seller_id, session)

@router.delete("/me/{product_id}", summary="Удалить товар", response_model=schemas.Response,
               responses={404: {"model": schemas.ErrorMessage}, 500: {"model": schemas.ErrorMessage}, 429: {"model": schemas.ErrorMessage}})
@limiter.limit("10/minute")
async def delete_product(request: Request, product_id: uuid.UUID, seller_id: uuid.UUID = Depends(verify_session), session: AsyncSession = Depends(get_session)):
    return await Products.delete_product(product_id, seller_id, session)

@router.post("/me/{product_id}/images", summary="Загрузить фото товара", response_model=schemas.ProductResponse,
             responses={400: {"model": schemas.ErrorMessage}, 404: {"model": schemas.ErrorMessage}, 500: {"model": schemas.ErrorMessage}, 429: {"model": schemas.ErrorMessage}})
@limiter.limit("10/minute")
async def upload_image(request: Request, product_id: uuid.UUID, file: UploadFile = File(...), seller_id: uuid.UUID = Depends(verify_session), session: AsyncSession = Depends(get_session)):
    return await Products.upload_image(product_id, file, seller_id, session)

@router.delete("/me/{product_id}/images/{image_index}", summary="Удалить фото товара", response_model=schemas.ProductResponse)
@limiter.limit("10/minute")
async def delete_product_image(request: Request, product_id: uuid.UUID, image_index: int, seller_id: uuid.UUID = Depends(verify_session), session: AsyncSession = Depends(get_session)):
    return await Products.delete_image(product_id, image_index, seller_id, session)