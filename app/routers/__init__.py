from fastapi import APIRouter

from .auth import router as auth_router
from .payments import router as payment_router

main_router = APIRouter()
main_router.include_router(auth_router, prefix="/auth", tags=["Auth"])
main_router.include_router(payment_router, prefix="/payments", tags=["Payments"])