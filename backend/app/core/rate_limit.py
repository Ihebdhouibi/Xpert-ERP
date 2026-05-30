"""Redis-based rate limiting dependencies for FastAPI endpoints."""
from __future__ import annotations

from typing import Callable

from fastapi import Depends, HTTPException, Request, status
from redis.asyncio import Redis

from app.core.redis import get_redis


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def rate_limit(key_prefix: str, max_requests: int, window_seconds: int) -> Callable:
    """
    Return a FastAPI dependency that enforces a sliding-window rate limit.

    Usage:
        @router.post("/login", dependencies=[rate_limit("auth:login", 10, 60)])
    """
    async def _check(request: Request, redis: Redis = Depends(get_redis)) -> None:
        ip = _client_ip(request)
        key = f"rl:{key_prefix}:{ip}"
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, window_seconds)
        if count > max_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please try again later.",
                headers={"Retry-After": str(window_seconds)},
            )

    return Depends(_check)
