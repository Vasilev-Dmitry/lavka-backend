import uuid
import io
import asyncio
import boto3
from urllib.parse import urlparse

from PIL import Image
from fastapi import HTTPException, status
from botocore.exceptions import BotoCoreError, ClientError
from app.config import settings

def _get_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.S3_URL,
        aws_access_key_id=settings.S3_KEY,
        aws_secret_access_key=settings.S3_SECRET,
        region_name=settings.S3_REGION,
    )

def _compress(file_bytes: bytes, max_size: tuple[int, int] = (1200, 1200), quality: int = 90) -> bytes:
    img = Image.open(io.BytesIO(file_bytes))
    img.thumbnail(max_size, Image.Resampling.LANCZOS)
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    output = io.BytesIO()
    img.save(output, format="WEBP", quality=quality)
    return output.getvalue()


def _upload(file_bytes: bytes, key: str) -> str:
    client = _get_client()
    compressed = _compress(file_bytes)
    client.upload_fileobj(
        io.BytesIO(compressed),
        settings.S3_BUCKET,
        key,
        ExtraArgs={"ContentType": "image/webp"},
    )
    return f"{settings.S3_URL}/{settings.S3_BUCKET}/{key}"


def _delete(key: str) -> None:
    client = _get_client()
    client.delete_object(Bucket=settings.S3_BUCKET, Key=key)


async def upload_image(file_bytes: bytes, folder: str) -> str:
    key = f"{folder}/{uuid.uuid4()}.webp"
    try:
        return await asyncio.to_thread(_upload, file_bytes, key)
    except (BotoCoreError, ClientError) as e:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"Failed to upload image: {e}")


async def delete_image(url: str) -> None:
    parsed = urlparse(url)
    bucket_prefix = f"/{settings.S3_BUCKET}/"
    key = parsed.path[len(bucket_prefix):] if parsed.path.startswith(bucket_prefix) else None
    if not key:
        return
    try:
        await asyncio.to_thread(_delete, key)
    except (BotoCoreError, ClientError):
        pass