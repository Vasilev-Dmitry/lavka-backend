import uuid
import httpx
import jwt as pyjwt
from datetime import datetime, UTC, timedelta
from app.config import settings
from fastapi import HTTPException
from sqlalchemy import select
from sentry_sdk import logger as sentry_logger
from app.database.models import Seller, Invoice

class Payments:
    @staticmethod
    async def create(request, seller_id: uuid.UUID, session):
        result = await session.execute(
            select(Seller).where(Seller.id == seller_id)
        )
        seller = result.scalar_one_or_none()

        if not seller:
            raise HTTPException(status_code=404, detail="Seller not found")

        if seller.is_subscribed:
            raise HTTPException(status_code=400, detail="Subscription already active")

        headers = {
            "Authorization": f"Token {settings.CRYPTOCLOUD_API_KEY}",
            "Content-Type": "application/json"
        }

        payload = {
            "shop_id": settings.CRYPTOCLOUD_SHOP_ID,
            "amount": settings.SUBSCRIPTION_PRICE,
            "currency": "USD",
            "email": seller.email,
            "add_fields": {
                "time_to_pay": { "hours": 1, "minutes": 0 },
            }
        }

        try:
            client = request.app.state.http_client
            response = await client.post(url=settings.CRYPTOCLOUD_CREATE_INVOICE, headers=headers, json=payload)
            response_data = response.json()

            if response.status_code != 200 or response_data.get("status") != "success":
                raise HTTPException(status_code=400, detail=f"CryptoCloud error: {response_data.get('message')}")

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

            return {"link": result_data["link"]}

        except HTTPException:
            raise
        except httpx.RequestError:
            raise HTTPException(status_code=503, detail="Payment service unavailable")
        except Exception as e:
            await session.rollback()
            sentry_logger.error("Failed to create invoice", attributes={"error": str(e), "seller_id": str(seller_id)})
            raise HTTPException(status_code=500, detail="Something went wrong")

    @staticmethod
    async def webhook(request, session):
        data = await request.json()

        token = data.get("token")
        if token:
            try:
                pyjwt.decode(token, settings.CRYPTOCLOUD_SECRET_KEY, algorithms=["HS256"])
            except pyjwt.PyJWTError:
                raise HTTPException(status_code=401, detail="Invalid token")

        if data.get("status") != "success":
            return {"message": "Postback received"}

        invoice_id = f"INV-{data.get('invoice_id')}"

        result = await session.execute(
            select(Invoice).where(Invoice.invoice_id == invoice_id)
        )
        invoice = result.scalar_one_or_none()

        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")

        if invoice.status == "paid":
            return {"message": "Postback received"}

        try:
            invoice.status = "paid"

            seller_result = await session.execute(
                select(Seller).where(Seller.id == invoice.seller_id)
            )
            seller = seller_result.scalar_one_or_none()

            if seller:
                seller.is_subscribed = True
                seller.subscription_expires_at = datetime.now(UTC) + timedelta(days=30)

            await session.commit()
            return {"message": "Postback received"}
        except Exception as e:
            await session.rollback()
            sentry_logger.error("Webhook processing failed", attributes={"error": str(e), "invoice_id": invoice_id})
            raise HTTPException(status_code=500, detail="Something went wrong")