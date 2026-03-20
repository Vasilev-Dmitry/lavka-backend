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

sentry_sdk.init(
    dsn=settings.SENTRY_DSN,
    send_default_pii=True,
)

app = FastAPI(title=settings.TITLE, version=settings.VERSION)
app.add_middleware(CORSMiddleware,
                   allow_origins=["http://localhost:3000", "https://accounts.google.com"],
                   allow_methods=["*"],
                   allow_headers=["*"],
                   allow_credentials=True)
app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.state.limiter = limiter

app.include_router(main_router)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, log_level="debug")