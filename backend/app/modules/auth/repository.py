"""Auth repository — all DB queries for the auth module."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.auth.models import AppUser, Permission, Role, RolePermission, UserRole


async def get_user_by_email(
    db: AsyncSession, garage_id: int, email: str
) -> Optional[AppUser]:
    result = await db.execute(
        select(AppUser).where(
            AppUser.garage_id == garage_id,
            AppUser.email == email,
            AppUser.deleted_at.is_(None),
        )
    )
    return result.scalar_one_or_none()


async def get_user_by_public_id(
    db: AsyncSession, public_id: str
) -> Optional[AppUser]:
    import uuid as _uuid
    try:
        uid = _uuid.UUID(public_id)
    except ValueError:
        return None
    result = await db.execute(
        select(AppUser).where(
            AppUser.public_id == uid,
            AppUser.deleted_at.is_(None),
        )
    )
    return result.scalar_one_or_none()


async def get_user_with_roles(
    db: AsyncSession, user_id: int
) -> Optional[AppUser]:
    """Load user with roles and their permissions eagerly."""
    result = await db.execute(
        select(AppUser)
        .options(
            selectinload(AppUser.user_roles)
            .selectinload(UserRole.role)
            .selectinload(Role.role_permissions)
            .selectinload(RolePermission.permission)
        )
        .where(AppUser.id == user_id, AppUser.deleted_at.is_(None))
    )
    return result.scalar_one_or_none()


async def increment_failed_logins(db: AsyncSession, user_id: int) -> int:
    result = await db.execute(
        update(AppUser)
        .where(AppUser.id == user_id)
        .values(failed_login_count=AppUser.failed_login_count + 1)
        .returning(AppUser.failed_login_count)
    )
    await db.flush()
    row = result.fetchone()
    return row[0] if row else 0


async def lock_user(
    db: AsyncSession, user_id: int, locked_until: datetime
) -> None:
    await db.execute(
        update(AppUser)
        .where(AppUser.id == user_id)
        .values(status="locked", locked_until=locked_until)
    )
    await db.flush()


async def reset_failed_logins(db: AsyncSession, user_id: int) -> None:
    await db.execute(
        update(AppUser)
        .where(AppUser.id == user_id)
        .values(failed_login_count=0, locked_until=None, last_login_at=datetime.utcnow())
    )
    await db.flush()


async def set_password_reset_token(
    db: AsyncSession,
    user_id: int,
    token_hash: str,
    expires_at: datetime,
) -> None:
    await db.execute(
        update(AppUser)
        .where(AppUser.id == user_id)
        .values(
            password_reset_token_hash=token_hash,
            password_reset_expires_at=expires_at,
        )
    )
    await db.flush()


async def update_password(
    db: AsyncSession,
    user_id: int,
    new_password_hash: str,
) -> None:
    await db.execute(
        update(AppUser)
        .where(AppUser.id == user_id)
        .values(
            password_hash=new_password_hash,
            password_reset_token_hash=None,
            password_reset_expires_at=None,
            failed_login_count=0,
            locked_until=None,
            status="active",
            version=AppUser.version + 1,
        )
    )
    await db.flush()


def collect_permissions(user: AppUser) -> list[str]:
    """Return deduplicated permission codes from all assigned roles."""
    codes: set[str] = set()
    for ur in user.user_roles:
        for rp in ur.role.role_permissions:
            codes.add(rp.permission.code)
    return sorted(codes)


def collect_role_codes(user: AppUser) -> list[str]:
    return [ur.role.code for ur in user.user_roles]
