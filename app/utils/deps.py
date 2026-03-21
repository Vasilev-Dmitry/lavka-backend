import uuid
from fastapi import Request, HTTPException
from app.utils.jwt_utils import decode_token

async def verify_session(
    request: Request,
) -> uuid.UUID:
    access_token = request.cookies.get("access_token")
    if not access_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    payload = decode_token(access_token)

    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token type")

    return uuid.UUID(payload["sub"])