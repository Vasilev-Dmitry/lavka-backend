from upstash_redis.asyncio import Redis
from app.config import settings

redis = Redis(url=settings.UPSTASH_REDIS_REST_URL, token=settings.UPSTASH_REDIS_REST_TOKEN)