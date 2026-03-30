from fastapi import APIRouter

from .payments import router as payment_router
from .auth import router as auth_router
from .profile import router as profile_router
from .shop import router as shop_router
from .products import router as product_router
from .showcase import router as showcase_router

main_router = APIRouter()
main_router.include_router(payment_router, prefix="/payments", tags=["Payments"])
main_router.include_router(auth_router, prefix="/auth", tags=["Auth"])
main_router.include_router(profile_router, tags=["Profile"])
main_router.include_router(shop_router, tags=["Shop"])
main_router.include_router(product_router, prefix="/products", tags=["Products"])
main_router.include_router(showcase_router, tags=["Showcase"])
