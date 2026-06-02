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


async def copy_object(*, bucket: str, source_key: str, dest_key: str) -> None:
    """Server-side copy within the same bucket (used by archiver)."""
    client = _make_client()
    loop = asyncio.get_running_loop()
    copy_source = {"Bucket": bucket, "Key": source_key}
    fn = functools.partial(
        client.copy_object,
        CopySource=copy_source,
        Bucket=bucket,
        Key=dest_key,
    )
    try:
        await loop.run_in_executor(None, fn)
    except ClientError as exc:
        logger.error("s3_copy_failed", source=source_key, dest=dest_key, error=str(exc))
        raise


async def delete_object(*, bucket: str, key: str) -> None:
    """Delete a single object from the bucket."""
    client = _make_client()
    loop = asyncio.get_running_loop()
    fn = functools.partial(client.delete_object, Bucket=bucket, Key=key)
    try:
        await loop.run_in_executor(None, fn)
    except ClientError as exc:
        logger.error("s3_delete_failed", key=key, error=str(exc))
        raise


async def download_object(*, bucket: str, key: str) -> bytes:
    """Download an object from S3 and return its raw bytes."""
    client = _make_client()
    loop = asyncio.get_running_loop()
    get = functools.partial(client.get_object, Bucket=bucket, Key=key)
    try:
        response = await loop.run_in_executor(None, get)
        body = response["Body"]
        read = functools.partial(body.read)
        return await loop.run_in_executor(None, read)
    except ClientError as exc:
        logger.error("s3_download_failed", key=key, error=str(exc))
        raise

