"""Credit limit change request endpoints.

Flow:
1. Staff without `customer.credit_limit.update` (e.g. receptionist) wants to
   change an existing customer's credit limit → POST /credit-limit-requests
2. Admin is notified in-app → GET /credit-limit-requests (pending list)
3. Admin approves → POST /credit-limit-requests/{id}/approve
   (applies the new limit to the customer immediately, with an audit entry)
   or rejects → POST /credit-limit-requests/{id}/reject
4. Requester is notified either way.

Unlike credit override requests (a one-time window to issue a single
document), approving a credit-limit change request permanently updates
`Customer.credit_limit_minor` / `credit_currency`.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.logging import get_logger
from app.modules.audit.service import audit
from app.modules.auth.models import AppUser
from app.modules.customer import repository as customer_repo
from app.modules.customer.models import CreditLimitChangeRequest, CreditLimitRequestStatus
from app.modules.customer.schemas import (
    CreditLimitChangeRejectBody,
    CreditLimitChangeRequestCreate,
    CreditLimitChangeRequestOut,
)
from app.modules.notification.inbox_router import create_app_notification
from app.modules.rbac.dependencies import AuthUser, require_permission

router = APIRouter(prefix="/credit-limit-requests", tags=["credit-limit-requests"])
logger = get_logger("customer.credit_limit_request")


async def _get_credit_limit_admin_ids(db: AsyncSession, garage_id: int) -> list[int]:
    """Return IDs of all users who have the customer.credit_limit.update permission."""
    from app.modules.auth.models import UserRole, Role, RolePermission, Permission

    result = await db.execute(
        select(AppUser.id)
        .join(UserRole, UserRole.user_id == AppUser.id)
        .join(Role, Role.id == UserRole.role_id)
        .join(RolePermission, RolePermission.role_id == Role.id)
        .join(Permission, Permission.id == RolePermission.permission_id)
        .where(
            AppUser.garage_id == garage_id,
            AppUser.deleted_at.is_(None),
            Permission.code == "customer.credit_limit.update",
        )
    )
    return [row[0] for row in result.all()]


def _to_out(req: CreditLimitChangeRequest, customer_name: Optional[str]) -> CreditLimitChangeRequestOut:
    return CreditLimitChangeRequestOut(
        id=req.id,
        customer_id=req.customer_id,
        customer_name=customer_name,
        requested_by_id=req.requested_by_id,
        current_credit_limit_minor=req.current_credit_limit_minor,
        requested_credit_limit_minor=req.requested_credit_limit_minor,
        requested_credit_currency=req.requested_credit_currency,
        reason=req.reason,
        status=req.status.value,
        approved_by_id=req.approved_by_id,
        rejection_reason=req.rejection_reason,
        created_at=req.created_at,
    )


@router.post(
    "",
    response_model=CreditLimitChangeRequestOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[require_permission("customer.update")],
    summary="Request a credit limit change for an existing customer",
)
async def create_credit_limit_change_request(
    user: AuthUser,
    body: CreditLimitChangeRequestCreate,
    db: AsyncSession = Depends(get_db),
) -> CreditLimitChangeRequestOut:
    customer = await customer_repo.get_by_public_id(db, user.garage_id, body.customer_public_id)
    if not customer:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Client introuvable.")

    dup_stmt = select(CreditLimitChangeRequest).where(
        CreditLimitChangeRequest.garage_id == user.garage_id,
        CreditLimitChangeRequest.customer_id == customer.id,
        CreditLimitChangeRequest.status == CreditLimitRequestStatus.pending,
    )
    existing = (await db.execute(dup_stmt)).scalar_one_or_none()
    if existing:
        return _to_out(existing, customer.full_name)

    req = CreditLimitChangeRequest(
        garage_id=user.garage_id,
        customer_id=customer.id,
        requested_by_id=user.user_id,
        current_credit_limit_minor=customer.credit_limit_minor,
        requested_credit_limit_minor=body.credit_limit_minor,
        requested_credit_currency=body.credit_currency,
        reason=body.reason,
        status=CreditLimitRequestStatus.pending,
    )
    db.add(req)
    await db.flush()

    admin_ids = await _get_credit_limit_admin_ids(db, user.garage_id)
    for admin_id in admin_ids:
        await create_app_notification(
            db,
            garage_id=user.garage_id,
            recipient_id=admin_id,
            title=f"Modification de limite de crédit demandée — {customer.full_name}",
            body=(
                f"Un utilisateur demande à modifier la limite de crédit de {customer.full_name} "
                f"({customer.credit_limit_minor / 100:.2f} → {body.credit_limit_minor / 100:.2f} "
                f"{body.credit_currency}). Votre approbation est requise."
            ),
            link=f"/credit-limit-requests/{req.id}",
        )

    await db.commit()
    await db.refresh(req)

    logger.info(
        "credit_limit_request_created",
        request_id=req.id,
        customer_id=customer.id,
        requested_by=user.user_id,
    )

    return _to_out(req, customer.full_name)


@router.get(
    "",
    response_model=list[CreditLimitChangeRequestOut],
    dependencies=[require_permission("customer.update")],
    summary=(
        "List credit limit change requests. Admins (customer.credit_limit.update) see all "
        "matching requests; other callers only see requests they submitted themselves."
    ),
)
async def list_credit_limit_change_requests(
    user: AuthUser,
    status_filter: Optional[str] = Query(None, alias="status"),
    customer_public_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
) -> list[CreditLimitChangeRequestOut]:
    stmt = select(CreditLimitChangeRequest).where(
        CreditLimitChangeRequest.garage_id == user.garage_id,
    )
    if not user.has_permission("customer.credit_limit.update"):
        stmt = stmt.where(CreditLimitChangeRequest.requested_by_id == user.user_id)
    if customer_public_id:
        customer = await customer_repo.get_by_public_id(db, user.garage_id, customer_public_id)
        if not customer:
            return []
        stmt = stmt.where(CreditLimitChangeRequest.customer_id == customer.id)
    if status_filter:
        stmt = stmt.where(CreditLimitChangeRequest.status == status_filter)
    else:
        stmt = stmt.where(CreditLimitChangeRequest.status == CreditLimitRequestStatus.pending)
    stmt = stmt.order_by(CreditLimitChangeRequest.created_at.desc())

    rows = (await db.execute(stmt)).scalars().all()

    out = []
    for r in rows:
        customer = await customer_repo.get_by_id(db, user.garage_id, r.customer_id)
        out.append(_to_out(r, customer.full_name if customer else None))
    return out


@router.get(
    "/{request_id}",
    response_model=CreditLimitChangeRequestOut,
    dependencies=[require_permission("customer.update")],
    summary="Get a single credit limit change request",
)
async def get_credit_limit_change_request(
    request_id: int,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> CreditLimitChangeRequestOut:
    stmt = select(CreditLimitChangeRequest).where(
        CreditLimitChangeRequest.id == request_id,
        CreditLimitChangeRequest.garage_id == user.garage_id,
    )
    if not user.has_permission("customer.credit_limit.update"):
        stmt = stmt.where(CreditLimitChangeRequest.requested_by_id == user.user_id)
    req = (await db.execute(stmt)).scalar_one_or_none()
    if not req:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Demande introuvable.")

    customer = await customer_repo.get_by_id(db, user.garage_id, req.customer_id)
    return _to_out(req, customer.full_name if customer else None)


@router.post(
    "/{request_id}/approve",
    response_model=CreditLimitChangeRequestOut,
    dependencies=[require_permission("customer.credit_limit.update")],
    summary="Approve a credit limit change request — applies the new limit (admin only)",
)
async def approve_credit_limit_change_request(
    request_id: int,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> CreditLimitChangeRequestOut:
    req = (
        await db.execute(
            select(CreditLimitChangeRequest).where(
                CreditLimitChangeRequest.id == request_id,
                CreditLimitChangeRequest.garage_id == user.garage_id,
            )
        )
    ).scalar_one_or_none()
    if not req:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Demande introuvable.")
    if req.status != CreditLimitRequestStatus.pending:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Cette demande n'est plus en attente.")

    customer = await customer_repo.get_by_id(db, user.garage_id, req.customer_id)
    if not customer:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Client introuvable.")

    old_value = {
        "credit_limit_minor": customer.credit_limit_minor,
        "credit_currency": customer.credit_currency,
    }
    customer.credit_limit_minor = req.requested_credit_limit_minor
    customer.credit_currency = req.requested_credit_currency
    customer.version += 1
    customer.updated_by_user_id = user.user_id

    req.status = CreditLimitRequestStatus.approved
    req.approved_by_id = user.user_id
    await db.flush()

    await audit(
        db=db,
        garage_id=user.garage_id,
        user_id=user.user_id,
        component="customer",
        action="credit_limit.update",
        entity_type="customer",
        entity_id=customer.id,
        old_value=old_value,
        new_value={
            "credit_limit_minor": customer.credit_limit_minor,
            "credit_currency": customer.credit_currency,
        },
        reason=f"Demande #{req.id} approuvée : {req.reason}",
    )

    await create_app_notification(
        db,
        garage_id=user.garage_id,
        recipient_id=req.requested_by_id,
        title=f"Limite de crédit approuvée — {customer.full_name}",
        body=(
            f"L'administrateur a approuvé la nouvelle limite de crédit de {customer.full_name} "
            f"({req.requested_credit_limit_minor / 100:.2f} {req.requested_credit_currency})."
        ),
        link=f"/customers/{customer.public_id}",
    )

    await db.commit()
    await db.refresh(req)

    logger.info("credit_limit_request_approved", request_id=req.id, approved_by=user.user_id)

    return _to_out(req, customer.full_name)


@router.post(
    "/{request_id}/reject",
    response_model=CreditLimitChangeRequestOut,
    dependencies=[require_permission("customer.credit_limit.update")],
    summary="Reject a credit limit change request (admin only)",
)
async def reject_credit_limit_change_request(
    request_id: int,
    user: AuthUser,
    body: CreditLimitChangeRejectBody,
    db: AsyncSession = Depends(get_db),
) -> CreditLimitChangeRequestOut:
    req = (
        await db.execute(
            select(CreditLimitChangeRequest).where(
                CreditLimitChangeRequest.id == request_id,
                CreditLimitChangeRequest.garage_id == user.garage_id,
            )
        )
    ).scalar_one_or_none()
    if not req:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Demande introuvable.")
    if req.status != CreditLimitRequestStatus.pending:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Cette demande n'est plus en attente.")

    req.status = CreditLimitRequestStatus.rejected
    req.approved_by_id = user.user_id
    req.rejection_reason = body.reason
    await db.flush()

    customer = await customer_repo.get_by_id(db, user.garage_id, req.customer_id)
    reason_text = f" Motif : {body.reason}" if body.reason else ""
    await create_app_notification(
        db,
        garage_id=user.garage_id,
        recipient_id=req.requested_by_id,
        title=f"Modification de limite de crédit refusée — {customer.full_name if customer else ''}",
        body=(
            f"L'administrateur a refusé la modification de limite de crédit demandée "
            f"pour {customer.full_name if customer else 'ce client'}.{reason_text}"
        ),
        link=f"/customers/{customer.public_id}" if customer else None,
    )

    await db.commit()
    await db.refresh(req)

    logger.info("credit_limit_request_rejected", request_id=req.id, rejected_by=user.user_id)

    return _to_out(req, customer.full_name if customer else None)
