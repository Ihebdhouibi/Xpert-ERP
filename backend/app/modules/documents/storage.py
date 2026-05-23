"""Object-storage abstraction (S3 / MinIO via boto3).

boto3 is synchronous; all calls are run in the default thread-pool executor
so they do not block the event loop.
"""
from __future__ import annotations

import asyncio
import functools
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger("documents.storage")

_CONNECT_TIMEOUT = 5   # seconds
_READ_TIMEOUT = 30     # seconds


def _make_client() -> Any:
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


async def upload_bytes(
    *,
    bucket: str,
    key: str,
    data: bytes,
    content_type: str,
) -> None:
    """Upload *data* to *bucket* under *key*.  Runs boto3 in executor."""
    client = _make_client()
    loop = asyncio.get_running_loop()
    put = functools.partial(
        client.put_object,
        Bucket=bucket,
        Key=key,
        Body=data,
        ContentType=content_type,
    )
    try:
        await loop.run_in_executor(None, put)
    except ClientError as exc:
        logger.error("s3_upload_failed", key=key, error=str(exc))
        raise


async def generate_presigned_url(
    *,
    bucket: str,
    key: str,
    expiry_seconds: int,
) -> str:
    """Return a pre-signed GET URL valid for *expiry_seconds*."""
    client = _make_client()
    loop = asyncio.get_running_loop()
    generate = functools.partial(
        client.generate_presigned_url,
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expiry_seconds,
    )
    try:
        url: str = await loop.run_in_executor(None, generate)
        return url
    except ClientError as exc:
        logger.error("s3_presign_failed", key=key, error=str(exc))
        raise
