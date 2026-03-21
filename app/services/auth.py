from app.database.cache import redis_set, redis_get, redis_delete
import uuid
from fastapi import HTTPException
from sqlalchemy import select
from app.database.models import Seller
from sentry_sdk import logger as sentry_logger
from app.config import settings

from app.utils.cookie import set_cookie
from app.utils.email import send_code
from app.utils.google import oauth
from app.utils.jwt_utils import decode_token

REFRESH_TTL = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60

class Auth:
    @staticmethod
    async def login(email: str):
        try:
            code = str(uuid.uuid4())
            await redis_set(f"verify:{code}", email, expire=900)
            await send_code(email, code)
            return {"success": True, "message": "Code sent successfully"}
        except Exception as e:
            sentry_logger.error(f"Failed to send code to {email}", attributes={"error": str(e)})
            raise HTTPException(status_code=500, detail="Something went wrong")

    @staticmethod
    async def verify(code: uuid.UUID, response, session):
        email = await redis_get(f"verify:{code}")
        if not email:
            raise HTTPException(status_code=401, detail="Invalid or expired link")

        try:
            result = await session.execute(
                select(Seller).where(Seller.email == email)
            )
            seller = result.scalar_one_or_none()

            if not seller:
                seller = Seller(email=email)
                session.add(seller)
                await session.commit()
                await session.refresh(seller)

            await redis_delete(f"verify:{code}")

            if not seller.is_active:
                raise HTTPException(status_code=403, detail="Account is blocked")

            refresh_token = set_cookie(response, uuid.UUID(str(seller.id)))
            await redis_set(f"refresh:{seller.id}", refresh_token, expire=REFRESH_TTL)

            return {"success": True, "message": "Successfully authenticated"}
        except HTTPException:
            raise
        except Exception as e:
            await session.rollback()
            sentry_logger.error(f"Authentication failed for {email}", attributes={"error": str(e)})
            raise HTTPException(status_code=500, detail="Authentication failed. Please try again later")

    @staticmethod
    async def refresh(request, response, session):
        refresh_token = request.cookies.get("refresh_token")
        if not refresh_token:
            raise HTTPException(status_code=401, detail="Refresh token missing")

        try:
            payload = decode_token(refresh_token)
        except HTTPException:
            response.delete_cookie("access_token")
            response.delete_cookie("refresh_token")
            raise HTTPException(status_code=401, detail="Session expired")

        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")

        seller_id = uuid.UUID(payload["sub"])

        stored_token = await redis_get(f"refresh:{seller_id}")
        if not stored_token or stored_token != refresh_token:
            raise HTTPException(status_code=401, detail="Session expired")

        result = await session.execute(select(Seller).where(Seller.id == seller_id))
        seller = result.scalar_one_or_none()

        if not seller or not seller.is_active:
            await redis_delete(f"refresh:{seller_id}")
            response.delete_cookie("access_token")
            response.delete_cookie("refresh_token")
            raise HTTPException(status_code=403, detail="Account is blocked")

        await redis_delete(f"refresh:{seller_id}")

        refresh_token = set_cookie(response, seller_id)
        await redis_set(f"refresh:{seller_id}", refresh_token, expire=REFRESH_TTL)

        return {"success": True, "message": "Tokens refreshed"}


    @staticmethod
    async def google_callback(request, response, session):
        try:
            token = await oauth.google.authorize_access_token(request)
        except Exception:
            raise HTTPException(status_code=400, detail="Google authorization failed")

        email = token["userinfo"]["email"]

        try:
            result = await session.execute(
                select(Seller).where(Seller.email == email)
            )
            seller = result.scalar_one_or_none()

            if not seller:
                seller = Seller(email=email)
                session.add(seller)
                await session.commit()
                await session.refresh(seller)

            if not seller.is_active:
                raise HTTPException(status_code=403, detail="Account is blocked")

            refresh_token = set_cookie(response, uuid.UUID(str(seller.id)))
            await redis_set(f"refresh:{seller.id}", refresh_token, expire=REFRESH_TTL)

            return {"success": True, "message": "Successfully authenticated"}
        except HTTPException:
            raise
        except Exception as e:
            await session.rollback()
            sentry_logger.error(f"Google auth failed for {email}", attributes={"error": str(e)})
            raise HTTPException(status_code=500, detail="Authentication failed. Please try again later")

    @staticmethod
    async def logout(request, response):
        refresh_token = request.cookies.get("refresh_token")
        if refresh_token:
            try:
                payload = decode_token(refresh_token)
                await redis_delete(f"refresh:{payload['sub']}")
            except HTTPException:
                pass

        response.delete_cookie("access_token")
        response.delete_cookie("refresh_token")
        return {"success": True, "message": "Successfully logged out"}