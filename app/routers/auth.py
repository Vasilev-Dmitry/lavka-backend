import app.schemas as schemas

from app.config import settings
from fastapi import APIRouter, Request, Response, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.limiter import limiter
from app.database.base import get_session
from app.services import Auth
from app.utils.google import oauth

router = APIRouter()

@router.post("/login", summary="Войти", response_model=schemas.Response,
             responses={500: {"model": schemas.ErrorMessage}, 429: {"model": schemas.ErrorMessage}})
@limiter.limit("5/minute")
async def login(request: Request, data: schemas.SellerLogin):
    return await Auth.login(str(data.email))

@router.post("/verify", summary="Проверить код из письма", response_model=schemas.Response,
             responses={401: {"model": schemas.ErrorMessage}, 403: {"model": schemas.ErrorMessage}, 500: {"model": schemas.ErrorMessage}, 429: {"model": schemas.ErrorMessage}})
@limiter.limit("5/minute")
async def verify(request: Request, response: Response, data: schemas.SellerVerify, session: AsyncSession = Depends(get_session)):
    return await Auth.verify(data.code, response, session)

@router.post("/refresh", summary="Обновить cookie", response_model=schemas.Response,
             responses={401: {"model": schemas.ErrorMessage}, 403: {"model": schemas.ErrorMessage}, 429: {"model": schemas.ErrorMessage}})
@limiter.limit("5/minute")
async def refresh(request: Request, response: Response, session: AsyncSession = Depends(get_session)):
    return await Auth.refresh(request, response, session)

@router.get("/google/login", summary="Войти с помощью Google", response_class=RedirectResponse,
            status_code=302, responses={429: {'model': schemas.ErrorMessage}})
@limiter.limit("5/minute")
async def google_login(request: Request):
    return await oauth.google.authorize_redirect(request, settings.GOOGLE_REDIRECT_URI)

@router.get("/google/callback", summary="Обработка ответа от Google", name="google_auth",
            response_class=RedirectResponse,
            responses={400: {'model': schemas.ErrorMessage}, 403: {'model': schemas.ErrorMessage}, 500: {"model": schemas.ErrorMessage}})
async def google_callback(request: Request, session: AsyncSession = Depends(get_session)):
    redirect = RedirectResponse(url="https://app.lavka.global", status_code=302)
    await Auth.google_callback(request, redirect, session)
    return redirect

@router.post("/logout", summary="Выйти", response_model=schemas.Response,
             responses={429: {"model": schemas.ErrorMessage}})
@limiter.limit("5/minute")
async def logout(request: Request, response: Response):
    return await Auth.logout(request, response)