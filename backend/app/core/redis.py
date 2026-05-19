"""
Redis connection pool.
"""

import redis.asyncio as aioredis

from app.core.config import get_settings

settings = get_settings()

_redis_pool: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis:
    """Return the shared Redis connection (lazily initialised)."""
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_pool


async def close_redis() -> None:
    global _redis_pool
    if _redis_pool is not None:
        await _redis_pool.aclose()
        _redis_pool = None
