import json
from redis.asyncio import from_url
from app.config import settings

redis = from_url(
    settings.REDIS_URL,
    encoding="utf-8",
    decode_responses=True,
)

async def redis_set(key: str, value, expire: int | None = None):
    await redis.set(key, json.dumps(value), ex=expire)

async def redis_get(key: str):
    raw = await redis.get(key)
    if raw is None:
        return None
    return json.loads(raw)

async def redis_delete(key: str):
    await redis.delete(key)