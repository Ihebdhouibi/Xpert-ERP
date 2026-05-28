"""S3/MinIO helpers for multipart uploads and object lifecycle operations.

All boto3 calls run in the default thread-pool executor (boto3 is sync).
"""
from __future__ import annotations

import asyncio
import functools
import io
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger("media.storage")

_CONNECT_TIMEOUT = 5
_READ_TIMEOUT = 60  # longer for large part uploads


def _client() -> Any:
    cfg = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=cfg.s3_endpoint_url,
        aws_access_key_id=cfg.s3_access_key_id,
        aws_secret_access_key=cfg.s3_secret_access_key,
        region_name=cfg.s3_region,
        config=Config(
            connect_timeout=_CONNECT_TIMEOUT,
            read_timeout=_READ_TIMEOUT,
            retries={"max_attempts": 3, "mode": "standard"},
        ),
    )


async def _run(fn: Any, *args: Any, **kwargs: Any) -> Any:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, functools.partial(fn, *args, **kwargs))


# ---------------------------------------------------------------------------
# Multipart upload lifecycle
# ---------------------------------------------------------------------------

async def create_multipart_upload(bucket: str, key: str, content_type: str) -> str:
    """Initiate a multipart upload; return the S3 UploadId."""
    c = _client()
    resp = await _run(
        c.create_multipart_upload,
        Bucket=bucket,
        Key=key,
        ContentType=content_type,
    )
    return str(resp["UploadId"])


async def upload_part(
    bucket: str,
    key: str,
    upload_id: str,
    part_number: int,
    data: bytes,
) -> str:
    """Upload one chunk; return the ETag."""
    c = _client()
    resp = await _run(
        c.upload_part,
        Bucket=bucket,
        Key=key,
        UploadId=upload_id,
        PartNumber=part_number,
        Body=data,
    )
    return str(resp["ETag"])


async def complete_multipart_upload(
    bucket: str,
    key: str,
    upload_id: str,
    parts: list[dict[str, Any]],
) -> None:
    """Complete the multipart upload.  parts = [{PartNumber, ETag}, ...]"""
    c = _client()
    await _run(
        c.complete_multipart_upload,
        Bucket=bucket,
        Key=key,
        UploadId=upload_id,
        MultipartUpload={"Parts": parts},
    )


async def abort_multipart_upload(bucket: str, key: str, upload_id: str) -> None:
    c = _client()
    try:
        await _run(c.abort_multipart_upload, Bucket=bucket, Key=key, UploadId=upload_id)
    except ClientError as exc:
        logger.warning("abort_multipart_failed", key=key, error=str(exc))


# ---------------------------------------------------------------------------
# Single-object operations
# ---------------------------------------------------------------------------

async def download_object(bucket: str, key: str) -> bytes:
    c = _client()
    resp = await _run(c.get_object, Bucket=bucket, Key=key)
    body = resp["Body"]
    # read() is sync; wrap it
    return await asyncio.get_running_loop().run_in_executor(None, body.read)


async def upload_bytes(
    bucket: str,
    key: str,
    data: bytes,
    content_type: str,
) -> None:
    c = _client()
    await _run(c.put_object, Bucket=bucket, Key=key, Body=data, ContentType=content_type)


async def copy_object(
    src_bucket: str,
    src_key: str,
    dst_bucket: str,
    dst_key: str,
) -> None:
    c = _client()
    await _run(
        c.copy_object,
        CopySource={"Bucket": src_bucket, "Key": src_key},
        Bucket=dst_bucket,
        Key=dst_key,
    )


async def delete_object(bucket: str, key: str) -> None:
    c = _client()
    try:
        await _run(c.delete_object, Bucket=bucket, Key=key)
    except ClientError as exc:
        logger.warning("delete_object_failed", key=key, error=str(exc))


async def generate_presigned_url(bucket: str, key: str, expiry_seconds: int) -> str:
    c = _client()
    return str(
        await _run(
            c.generate_presigned_url,
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expiry_seconds,
        )
    )


# ---------------------------------------------------------------------------
# EXIF stripping (server-side defence-in-depth for JPEG/PNG/WebP)
# ---------------------------------------------------------------------------

def strip_exif_sync(data: bytes, mime_type: str) -> bytes:
    """Re-encode image data without any metadata.  Runs synchronously (call via executor)."""
    if mime_type not in ("image/jpeg", "image/png", "image/webp"):
        return data
    try:
        from PIL import Image  # imported lazily to keep startup fast

        img = Image.open(io.BytesIO(data))
        # Convert palette / transparency modes to a safe target for JPEG
        if mime_type == "image/jpeg" and img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        out = io.BytesIO()
        fmt_map = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}
        img.save(out, format=fmt_map[mime_type])
        return out.getvalue()
    except Exception as exc:  # noqa: BLE001
        logger.warning("exif_strip_failed", mime=mime_type, error=str(exc))
        return data  # pass through unchanged rather than break the upload


async def strip_exif(data: bytes, mime_type: str) -> bytes:
    """Async wrapper around strip_exif_sync."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, strip_exif_sync, data, mime_type)
