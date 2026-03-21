import asyncio
from datetime import datetime, UTC, timedelta
from sqlalchemy import select
from app.database.base import async_session
from app.database.models import Seller
from sentry_sdk import logger as sentry_logger
import resend
from app.config import settings

resend.api_key = settings.RESEND_API_KEY

async def check_subscriptions():
    async with async_session() as session:
        try:
            now = datetime.now(UTC)

            # Подписки истекают через 7 дней
            in_7_days = now + timedelta(days=7)
            result = await session.execute(
                select(Seller).where(
                    Seller.is_subscribed == True,
                    Seller.subscription_expires_at >= in_7_days - timedelta(hours=12),
                    Seller.subscription_expires_at <= in_7_days + timedelta(hours=12),
                )
            )
            for seller in result.scalars().all():
                await asyncio.to_thread(resend.Emails.send, {
                    "from": "Lavka <hello@lavka.global>",
                    "to": [seller.email],
                    "subject": "Подписка истекает через 7 дней",
                    "text": "Ваша подписка истекает через 7 дней. Продлите её чтобы продолжить пользоваться сервисом."
                })

            # Подписки истекают через 2 дня
            in_2_days = now + timedelta(days=2)
            result = await session.execute(
                select(Seller).where(
                    Seller.is_subscribed == True,
                    Seller.subscription_expires_at >= in_2_days - timedelta(hours=12),
                    Seller.subscription_expires_at <= in_2_days + timedelta(hours=12),
                )
            )
            for seller in result.scalars().all():
                await asyncio.to_thread(resend.Emails.send, {
                    "from": "Lavka <hello@lavka.global>",
                    "to": [seller.email],
                    "subject": "Подписка истекает через 2 дня",
                    "text": "Ваша подписка истекает через 2 дня. Продлите её чтобы не потерять доступ."
                })

            # Подписки истекли
            result = await session.execute(
                select(Seller).where(
                    Seller.is_subscribed == True,
                    Seller.subscription_expires_at < now,
                )
            )
            for seller in result.scalars().all():
                seller.is_subscribed = False
                await asyncio.to_thread(resend.Emails.send, {
                    "from": "Lavka <hello@lavka.global>",
                    "to": [seller.email],
                    "subject": "Подписка истекла",
                    "text": "Ваша подписка истекла. Продлите её чтобы продолжить пользоваться сервисом."
                })

            await session.commit()
        except Exception as e:
            await session.rollback()
            sentry_logger.error("Subscription check failed", attributes={"error": str(e)})