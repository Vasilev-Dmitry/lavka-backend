import uuid
import json

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database.cache import redis
from fastapi import HTTPException, Request, status, Response as FastApiResponse
from app.database.models import Seller
from sentry_sdk import logger as sentry_logger
from app.config import settings
from app.schemas import Response, SellerResponse
from app.utils.cookie import set_cookie
from app.utils.email import send_code
from app.utils.google import oauth
from app.utils.jwt_utils import decode_token

class Auth:
    @staticmethod
    async def _authenticate_user(email: str, response: FastApiResponse, session: AsyncSession) -> Response:
        seller = (await session.execute(select(Seller).where(Seller.email == email))).scalar_one_or_none()

        if not seller:
            seller = Seller(email=email)
            session.add(seller)
            await session.commit()
            await session.refresh(seller)

        if not seller.is_active:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Account is blocked")

        await redis.set(f"seller:{seller.id}", SellerResponse.model_validate(seller).model_dump_json(), ex=600)
        await redis.set(f"refresh:{seller.id}", set_cookie(response, seller.id), ex=settings.REFRESH_TOKEN_EXPIRE_TIME)

        return Response(success=True, message="Successfully authenticated")

    @staticmethod
    async def login(email: str) -> Response:
        try:
            code = str(uuid.uuid4())
            await redis.set(f"verify:{code}", email, ex=900)
            await send_code(email, code)
            return Response(success=True, message="Code sent successfully")
        except Exception as e:
            sentry_logger.error(f"Failed to send code to {email}", attributes={"error": str(e)})
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Something went wrong")

    @staticmethod
    async def verify(code: uuid.UUID, response: FastApiResponse, session: AsyncSession) -> Response:
        email = await redis.get(f"verify:{code}")
        if not email:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired link")
        try:
            result = await Auth._authenticate_user(email, response, session)
            await redis.delete(f"verify:{code}")
            return result
        except HTTPException:
            raise
        except Exception as e:
            sentry_logger.error(f"Authentication failed for {email}", attributes={"error": str(e)})
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Authentication failed. Please try again later")

    @staticmethod
    def _clear_session(response: FastApiResponse):
        response.delete_cookie("access_token")
        response.delete_cookie("refresh_token")

    @staticmethod
    async def refresh(request: Request, response: FastApiResponse, session: AsyncSession) -> Response:
        refresh_token = request.cookies.get("refresh_token")
        if not refresh_token:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Refresh token missing")

        try:
            payload = decode_token(refresh_token)
        except HTTPException:
            Auth._clear_session(response)
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Session expired")

        if payload.get("type") != "refresh":
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

        seller_id = uuid.UUID(payload["sub"])

        if not (stored := await redis.get(f"refresh:{seller_id}")) or stored != refresh_token:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Session expired")

        cached = await redis.get(f"seller:{seller_id}")
        if cached:
            if not json.loads(cached).get("is_active"):
                await redis.delete(f"refresh:{seller_id}")
                Auth._clear_session(response)
                raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Account is blocked")
        else:
            seller = await session.get(Seller, seller_id)
            if not seller or not seller.is_active:
                await redis.delete(f"refresh:{seller_id}")
                Auth._clear_session(response)
                raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Account is blocked")

        await redis.delete(f"refresh:{seller_id}")
        await redis.set(f"refresh:{seller_id}", set_cookie(response, seller_id), ex=settings.REFRESH_TOKEN_EXPIRE_TIME)

        return Response(success=True, message="Tokens refreshed")

    @staticmethod
    async def google_callback(request: Request, response: FastApiResponse, session: AsyncSession) -> Response:
        try:
            token = await oauth.google.authorize_access_token(request)
            user_info = token.get("userinfo")
            if not user_info or not user_info.get("email_verified"):
                raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Google email not verified")
            return await Auth._authenticate_user(user_info["email"], response, session)
        except HTTPException:
            raise
        except Exception as e:
            sentry_logger.error(f"Google auth failed", attributes={"error": str(e)})
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Authentication failed. Please try again later")

    @staticmethod
    async def logout(request: Request, response: FastApiResponse) -> Response:
        if refresh_token := request.cookies.get("refresh_token"):
            try:
                if seller_id := decode_token(refresh_token).get("sub"):
                    await redis.delete(f"refresh:{seller_id}")
            except HTTPException:
                pass
        Auth._clear_session(response)
        return Response(success=True, message="Successfully logged out")