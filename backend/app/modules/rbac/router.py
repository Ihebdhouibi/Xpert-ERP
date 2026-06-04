"""User management endpoints (admin only)."""
from __future__ import annotations

import math
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.modules.auth.models import AppUser, Role, UserRole
from app.modules.auth.repository import collect_role_codes
from app.modules.auth.service import hash_password
from app.modules.rbac.dependencies import AuthUser, require_permission
from app.modules.rbac.schemas import (
    RoleAssignRequest,
    UserCreateRequest,
    UserListResponse,
    UserSummary,
    UserUpdateRequest,
)
from app.core.logging import get_logger

router = APIRouter(prefix="/users", tags=["users"])
logger = get_logger("rbac.router")


@router.get(
    "",
    response_model=UserListResponse,
    dependencies=[require_permission("users.read")],
    summary="List users in the current garage",
)
async def list_users(
    user: AuthUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> UserListResponse:
    offset = (page - 1) * page_size

    count_result = await db.execute(
        select(func.count(AppUser.id)).where(
            AppUser.garage_id == user.garage_id,
            AppUser.deleted_at.is_(None),
        )
    )
    total = count_result.scalar_one()

    result = await db.execute(
        select(AppUser)
        .options(
            selectinload(AppUser.user_roles)
            .selectinload(UserRole.role)
        )
        .where(AppUser.garage_id == user.garage_id, AppUser.deleted_at.is_(None))
        .order_by(AppUser.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    users = result.scalars().all()

    items = [
        UserSummary(
            id=str(u.public_id),
            garage_id=u.garage_id,
            email=u.email,
            full_name=u.full_name,
            status=u.status.value,
            roles=collect_role_codes(u),
            last_login_at=u.last_login_at,
            created_at=u.created_at,
        )
        for u in users
    ]
    return UserListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post(
    "",
    response_model=UserSummary,
    status_code=status.HTTP_201_CREATED,
    dependencies=[require_permission("users.create")],
    summary="Create a new user in the current garage",
)
async def create_user(
    body: UserCreateRequest,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> UserSummary:
    # Check for duplicate email within garage
    existing = await db.execute(
        select(AppUser).where(
            AppUser.garage_id == user.garage_id,
            AppUser.email == body.email,
            AppUser.deleted_at.is_(None),
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists in the garage.",
        )

    new_user = AppUser(
        garage_id=user.garage_id,
        email=body.email,
        full_name=body.full_name,
        password_hash=hash_password(body.password),
    )
    db.add(new_user)
    await db.flush()  # get the generated id

    # Assign roles
    if body.role_codes:
        roles_result = await db.execute(
            select(Role).where(Role.code.in_(body.role_codes))
        )
        roles = roles_result.scalars().all()
        for role in roles:
            db.add(UserRole(user_id=new_user.id, role_id=role.id, assigned_by=None))

    await db.commit()
    await db.refresh(new_user)

    # Reload with roles for response
    result = await db.execute(
        select(AppUser)
        .options(selectinload(AppUser.user_roles).selectinload(UserRole.role))
        .where(AppUser.id == new_user.id)
    )
    created = result.scalar_one()

    return UserSummary(
        id=str(created.public_id),
        garage_id=created.garage_id,
        email=created.email,
        full_name=created.full_name,
        status=created.status.value,
        roles=collect_role_codes(created),
        last_login_at=created.last_login_at,
        created_at=created.created_at,
    )


@router.patch(
    "/{public_id}",
    response_model=UserSummary,
    dependencies=[require_permission("users.update")],
    summary="Update user details",
)
async def update_user(
    public_id: str,
    body: UserUpdateRequest,
    actor: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> UserSummary:
    import uuid as _uuid
    result = await db.execute(
        select(AppUser)
        .options(selectinload(AppUser.user_roles).selectinload(UserRole.role))
        .where(
            AppUser.public_id == _uuid.UUID(public_id),
            AppUser.garage_id == actor.garage_id,
            AppUser.deleted_at.is_(None),
        )
    )
    target = result.scalar_one_or_none()
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if body.full_name is not None:
        target.full_name = body.full_name
    if body.status is not None:
        target.status = body.status  # type: ignore[assignment]
    target.version += 1

    await db.commit()
    await db.refresh(target)

    return UserSummary(
        id=str(target.public_id),
        garage_id=target.garage_id,
        email=target.email,
        full_name=target.full_name,
        status=target.status.value,
        roles=collect_role_codes(target),
        last_login_at=target.last_login_at,
        created_at=target.created_at,
    )


@router.post(
    "/{public_id}/roles",
    response_model=UserSummary,
    dependencies=[require_permission("roles.assign")],
    summary="Replace role assignments for a user",
)
async def assign_roles(
    public_id: str,
    body: RoleAssignRequest,
    actor: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> UserSummary:
    import uuid as _uuid
    result = await db.execute(
        select(AppUser)
        .options(selectinload(AppUser.user_roles))
        .where(
            AppUser.public_id == _uuid.UUID(public_id),
            AppUser.garage_id == actor.garage_id,
            AppUser.deleted_at.is_(None),
        )
    )
    target = result.scalar_one_or_none()
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Remove existing role assignments
    for ur in list(target.user_roles):
        await db.delete(ur)
    await db.flush()

    # Add new ones
    roles_result = await db.execute(
        select(Role).where(Role.code.in_(body.role_codes))
    )
    roles = roles_result.scalars().all()
    found_codes = {r.code for r in roles}
    missing = set(body.role_codes) - found_codes
    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown role codes: {sorted(missing)}",
        )

    for role in roles:
        db.add(UserRole(user_id=target.id, role_id=role.id, assigned_by=None))

    await db.commit()

    # Reload for response
    result2 = await db.execute(
        select(AppUser)
        .options(selectinload(AppUser.user_roles).selectinload(UserRole.role))
        .where(AppUser.id == target.id)
    )
    updated = result2.scalar_one()

    return UserSummary(
        id=str(updated.public_id),
        garage_id=updated.garage_id,
        email=updated.email,
        full_name=updated.full_name,
        status=updated.status.value,
        roles=collect_role_codes(updated),
        last_login_at=updated.last_login_at,
        created_at=updated.created_at,
    )


@router.delete(
    "/{public_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    dependencies=[require_permission("users.deactivate")],
    summary="Soft-delete (deactivate) a user",
)
async def deactivate_user(
    public_id: str,
    actor: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> Response:
    import uuid as _uuid
    from datetime import datetime, timezone
    result = await db.execute(
        select(AppUser).where(
            AppUser.public_id == _uuid.UUID(public_id),
            AppUser.garage_id == actor.garage_id,
            AppUser.deleted_at.is_(None),
        )
    )
    target = result.scalar_one_or_none()
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if str(target.public_id) == actor.public_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate your own account.",
        )

    target.deleted_at = datetime.now(tz=timezone.utc)
    target.status = "inactive"  # type: ignore[assignment]
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
