"""RBAC FastAPI dependency — require_permission() and current_user."""
from __future__ import annotations

from typing import Annotated, Any, Optional


from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import PyJWTError as JWTError
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis import get_redis
from app.modules.auth.service import decode_token, is_token_denied

_bearer = HTTPBearer(auto_error=False)


class CurrentUser:
    """Resolved from the JWT on every protected request."""

    def __init__(
        self,
        public_id: str,
        garage_id: int,
        roles: list[str],
        permissions: list[str],
        user_id: int = 0,
    ) -> None:
        self.public_id = public_id
        self.user_id = user_id
        self.garage_id = garage_id
        self.roles = roles
        self.permissions = permissions

    def has_permission(self, code: str) -> bool:
        return code in self.permissions

    def has_role(self, code: str) -> bool:
        return code in self.roles


async def _resolve_current_user(
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(_bearer)],
    redis: Redis = Depends(get_redis),
) -> CurrentUser:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = credentials.credentials
    try:
        payload: dict[str, Any] = decode_token(token, expected_type="access")
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    jti: str = payload.get("jti", "")
    if jti and await is_token_denied(redis, jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = CurrentUser(
        public_id=payload["sub"],
        user_id=payload.get("uid", 0),
        garage_id=payload["gid"],
        roles=payload.get("roles", []),
        permissions=payload.get("perms", []),
    )
    return user


# Convenience type alias for injection
AuthUser = Annotated[CurrentUser, Depends(_resolve_current_user)]


def require_permission(permission_code: str) -> Any:
    """
    FastAPI dependency factory. Usage:

        @router.get("/resource")
        async def endpoint(
            _: Annotated[None, Depends(require_permission("resource.read"))],
            user: AuthUser,
        ): ...
    """

    async def _check(user: AuthUser) -> None:
        if not user.has_permission(permission_code):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission required: {permission_code}",
            )

    return Depends(_check)


def require_role(role_code: str) -> Any:
    """Require a specific role (use sparingly — prefer permission checks)."""

    async def _check(user: AuthUser) -> None:
        if not user.has_role(role_code):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role required: {role_code}",
            )

    return Depends(_check)
