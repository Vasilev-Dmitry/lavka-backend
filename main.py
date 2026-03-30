from contextlib import asynccontextmanager

import httpx

from app.limiter import limiter
from app.routers import main_router
from app.config import settings

import uvicorn
import sentry_sdk
from slowapi.errors import RateLimitExceeded
from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.executors.asyncio import AsyncIOExecutor
from app.utils.subscriptions import check_subscriptions, check_expired_invoices

sentry_sdk.init(
    dsn=settings.SENTRY_DSN,
    send_default_pii=True,
)

@asynccontextmanager
async def lifespan(application: FastAPI):
    application.state.http_client = httpx.AsyncClient()

    scheduler = AsyncIOScheduler(timezone="UTC", executors={"default": AsyncIOExecutor()})
    scheduler.add_job(check_subscriptions, "cron", hour=9, minute=0)
    scheduler.add_job(check_expired_invoices, "interval", minutes=30)
    scheduler.start()

    yield

    scheduler.shutdown()
    await application.state.http_client.aclose()

origins = [settings.FRONTEND_URL, "https://accounts.google.com"]
if settings.EXTRA_CORS_ORIGINS:
    origins += [o.strip() for o in settings.EXTRA_CORS_ORIGINS.split(",") if o.strip()]

app = FastAPI(title=settings.TITLE, version=settings.VERSION, lifespan=lifespan)
app.add_middleware(CORSMiddleware,
                   allow_origins=origins,
                   allow_origin_regex=r"https://[a-zA-Z0-9-]+\.lavka\.global",
                   allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
                   allow_headers=["*"],
                   allow_credentials=True)
app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.state.limiter = limiter

app.include_router(main_router)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, log_level="debug")