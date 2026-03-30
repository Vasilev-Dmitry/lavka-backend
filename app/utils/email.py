import asyncio
import resend
from app.config import settings

resend.api_key = settings.RESEND_API_KEY

async def send_code(email: str, code: str):
    await asyncio.to_thread(resend.Emails.send, {
        "from": "Lavka <hello@lavka.global>",
        "to": [email],
        "subject": "Ваш код входа",
        "text": f"Ваш код: {code}"
    })