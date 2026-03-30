import jwt
import uuid
from fastapi import HTTPException
from app.config import settings
from datetime import datetime, timedelta, UTC

secret = settings.SECRET_KEY
algorithm = settings.ALGORITHM

access_token_expires = settings.ACCESS_TOKEN_EXPIRE_TIME
refresh_token_expires = settings.REFRESH_TOKEN_EXPIRE_TIME

def create_access_token(seller_id: uuid.UUID) -> str:
    payload = {
        "sub": str(seller_id),
        "exp": datetime.now(UTC) + timedelta(seconds=access_token_expires),
        "type": "access"
    }
    return jwt.encode(payload, secret, algorithm=algorithm)

def create_refresh_token(seller_id: uuid.UUID) -> str:
    payload = {
        "sub": str(seller_id),
        "exp": datetime.now(UTC) + timedelta(seconds=refresh_token_expires),
        "type": "refresh"
    }
    return jwt.encode(payload, secret, algorithm=algorithm)

def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, secret, algorithms=[algorithm])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")