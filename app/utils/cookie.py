import uuid
from app.utils.jwt_utils import create_access_token, create_refresh_token
from app.config import settings

def set_cookie(response, seller_id: uuid.UUID):
    refresh_token = create_refresh_token(seller_id)

    response.set_cookie(
        key="access_token",
        value=create_access_token(seller_id),
        httponly=True,
        expires=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax",
        secure=settings.IS_PRODUCTION,
        path="/"
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        expires=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        samesite="lax",
        secure=settings.IS_PRODUCTION,
        path="/"
    )

    return refresh_token