import uuid
import httpx
import json
import jwt

from datetime import datetime, UTC, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.schemas import InvoiceCreated
from fastapi import HTTPException, Request, status
from sqlalchemy import select
from sentry_sdk import logger as sentry_logger
from app.database.models import Seller, Invoice
from app.database.cache import redis
from app.constants import SUBSCRIPTION_PRICE

class Payments:
    @staticmethod
    def _headers() -> dict:
        return {
            "Authorization": f"Token {settings.CRYPTOCLOUD_API_KEY}",
            "Content-Type": "application/json"
        }

    @staticmethod
    async def create(request: Request, seller_id: uuid.UUID, session: AsyncSession) -> InvoiceCreated:
        data = await redis.get(f"seller:{seller_id}")
        if data:
            seller_data = json.loads(data)
            if seller_data.get("is_subscribed"):
                raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Subscription already active")
            seller_email = seller_data.get("email")
        else:
            seller = await session.get(Seller, seller_id)
            if not seller:
                raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Seller not found")
            if seller.is_subscribed:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Subscription already active")
            seller_email = seller.email

        existing = await session.execute(
            select(Invoice).where(
                Invoice.seller_id == seller_id,
                Invoice.status == "pending",
                Invoice.expires_at > datetime.now(UTC)
            )
        )
        invoice = existing.scalar_one_or_none()
        if invoice:
            return InvoiceCreated(link=f"https://pay.cryptocloud.plus/{invoice.invoice_id.removeprefix("INV-")}")

        payload = {
            "shop_id": settings.CRYPTOCLOUD_SHOP_ID,
            "amount": SUBSCRIPTION_PRICE,
            "currency": "USD",
            "email": seller_email,
            "add_fields": {
            "time_to_pay": { "hours": 1, "minutes": 0 },
            }
        }

        try:
            client = request.app.state.http_client
            response = await client.post(url=settings.CRYPTOCLOUD_CREATE_INVOICE, headers=Payments._headers(), json=payload)
            response_data = response.json()

            if response.status_code != 200 or response_data.get("status") != "success":
                raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"CryptoCloud error: {response_data.get('message')}")

            result_data = response_data["result"]

            invoice = Invoice(
                seller_id=seller_id,
                invoice_id=result_data["uuid"],
                amount=result_data["amount_usd"],
                currency=result_data["fiat_currency"],
                status="pending",
                expires_at=datetime.fromisoformat(result_data["expiry_date"])
            )
            session.add(invoice)
            await session.commit()

            return InvoiceCreated(link=result_data["link"])

        except HTTPException:
            raise
        except httpx.RequestError:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail="Payment service unavailable")
        except Exception as e:
            await session.rollback()
            sentry_logger.error("Failed to create invoice", attributes={"error": str(e), "seller_id": str(seller_id)})
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Something went wrong")

    @staticmethod
    async def webhook(request: Request, session: AsyncSession):
        data = await request.json()

        token = data.get("token")
        if token:
            try:
                jwt.decode(token, settings.CRYPTOCLOUD_SECRET_KEY, algorithms=["HS256"])
            except jwt.PyJWTError:
                raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

        if data.get("status") != "success":
            return {"message": "Postback received"}

        invoice_id = f"INV-{data.get('invoice_id')}"

        result = await session.execute(
            select(Invoice).where(Invoice.invoice_id == invoice_id)
        )
        invoice = result.scalar_one_or_none()
        if not invoice:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Invoice not found")

        if invoice.status == "paid":
            return {"message": "Postback received"}

        try:
            invoice.status = "paid"

            seller = await session.get(Seller, invoice.seller_id)
            if seller:
                seller.is_subscribed = True
                seller.subscription_expires_at = datetime.now(UTC) + timedelta(days=30)
                await session.commit()
                await redis.delete(f"seller:{seller.id}")
                await redis.delete(f"shop:{seller.id}")

            return {"message": "Postback received"}
        except Exception as e:
            await session.rollback()
            sentry_logger.error("Webhook processing failed", attributes={"error": str(e), "invoice_id": invoice_id})
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Something went wrong")