"""Auth router — login, refresh, logout, password reset endpoints."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.rate_limit import rate_limit
from app.core.redis import get_redis
from app.modules.auth import service
from app.modules.auth.schemas import (
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshRequest,
    TokenResponse,
)
from app.modules.notification.adapter import EmailAdapter
from app.core.logging import get_logger

router = APIRouter(prefix="/auth", tags=["auth"])
logger = get_logger("auth.router")


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post(
    "/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate and receive access + refresh tokens",
    dependencies=[rate_limit("auth:login", max_requests=10, window_seconds=60)],
)
async def login(
    body: LoginRequest,
    request: Request,
    x_garage_id: Annotated[int | None, Header(alias="X-Garage-ID")] = None,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> LoginResponse:
    garage_id = x_garage_id or 1  # TODO: resolve from subdomain/JWT in multi-garage setup
    try:
        return await service.login(
            db=db,
            redis=redis,
            email=body.email,
            password=body.password,
            garage_id=garage_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


@router.post(
    "/refresh",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    summary="Rotate refresh token and issue new access token",
    dependencies=[rate_limit("auth:refresh", max_requests=30, window_seconds=60)],
)
async def refresh(
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> LoginResponse:
    try:
        return await service.refresh(db=db, redis=redis, refresh_token_str=body.refresh_token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Revoke refresh token",
)
async def logout(
    body: LogoutRequest,
    redis: Redis = Depends(get_redis),
) -> Response:
    await service.logout(redis=redis, refresh_token_str=body.refresh_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/password-reset/request",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Request a password reset email",
    dependencies=[rate_limit("auth:pw-reset", max_requests=5, window_seconds=300)],
)
async def password_reset_request(
    body: PasswordResetRequest,
    request: Request,
    x_garage_id: Annotated[int | None, Header(alias="X-Garage-ID")] = None,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    garage_id = x_garage_id or 1
    raw_token = await service.request_password_reset(
        db=db, garage_id=garage_id, email=body.email
    )

    if raw_token:
        cfg = get_settings()
        reset_url = (
            f"{cfg.frontend_base_url}/reset-password"
            f"?token={raw_token}&email={body.email}"
        )
        html_body = f"""
        <p>Bonjour,</p>
        <p>Vous avez demandé la réinitialisation de votre mot de passe Xpert&nbsp;ERP.</p>
        <p>
          <a href="{reset_url}" style="
            display:inline-block;
            padding:10px 20px;
            background:#1976D2;
            color:#fff;
            text-decoration:none;
            border-radius:4px;
            font-weight:bold;
          ">Réinitialiser mon mot de passe</a>
        </p>
        <p>Ce lien expire dans {cfg.password_reset_expiry_minutes} minutes.</p>
        <p>Si vous n'êtes pas à l'origine de cette demande, ignorez cet email.</p>
        <hr/>
        <p style="font-size:12px;color:#666;">
          Lien direct : {reset_url}
        </p>
        """
        result = await EmailAdapter().send(
            recipient=body.email,
            channel="email",
            subject="Réinitialisation de votre mot de passe — Xpert ERP",
            body=html_body,
        )
        if not result.success:
            logger.warning(
                "password_reset_email_failed",
                email=body.email,
                error=result.error,
            )

    # Always return 202 — never reveal whether the email exists
    return {"detail": "If the email is registered, a reset link has been sent."}


@router.post(
    "/password-reset/confirm",
    status_code=status.HTTP_200_OK,
    summary="Confirm password reset with token",
    dependencies=[rate_limit("auth:pw-reset", max_requests=5, window_seconds=300)],
)
async def password_reset_confirm(
    body: PasswordResetConfirm,
    x_garage_id: Annotated[int | None, Header(alias="X-Garage-ID")] = None,
    x_reset_email: Annotated[str | None, Header(alias="X-Reset-Email")] = None,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    if not x_reset_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Reset-Email header is required",
        )
    garage_id = x_garage_id or 1
    try:
        await service.confirm_password_reset(
            db=db,
            garage_id=garage_id,
            email=x_reset_email,
            raw_token=body.token,
            new_password=body.new_password,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return {"detail": "Password updated successfully."}
