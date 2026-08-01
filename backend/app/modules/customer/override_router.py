"""Credit override request endpoints.

Flow:
1. Staff hits credit limit on invoice/BL issue → POST /credit-override-requests
2. Admin is notified in-app → GET /credit-override-requests (pending list)
3. Admin approves → POST /credit-override-requests/{id}/approve
4. Staff is notified → retries the issue action (override valid for 24 h)
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.logging import get_logger
from app.modules.auth.models import AppUser
from app.modules.customer import repository as customer_repo
from app.modules.customer.credit_service import OVERRIDE_WINDOW_HOURS
from app.modules.customer.models import CreditOverrideRequest, OverrideStatus
from app.modules.notification.inbox_router import create_app_notification
from app.modules.rbac.dependencies import AuthUser, require_permission

router = APIRouter(prefix="/credit-override-requests", tags=["credit-override"])
logger = get_logger("customer.override")


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class OverrideRequestCreate(BaseModel):
    customer_public_id: str
    doc_type: str  # "invoice" | "delivery_note"
    source_document_public_id: Optional[str] = None  # public_id of the specific BL or invoice being issued


class OverrideRequestOut(BaseModel):
    id: int
    customer_id: int
    customer_name: Optional[str] = None
    requested_by_id: int
    doc_type: str
    status: str
    approved_by_id: Optional[int] = None
    expires_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class RejectBody(BaseModel):
    reason: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_admin_ids(db: AsyncSession, garage_id: int) -> list[int]:
    """Return IDs of all users who have the credit.override.manage permission."""
    from app.modules.auth.models import UserRole, Role, RolePermission, Permission
    from sqlalchemy.orm import selectinload

    result = await db.execute(
        select(AppUser.id)
        .join(UserRole, UserRole.user_id == AppUser.id)
        .join(Role, Role.id == UserRole.role_id)
        .join(RolePermission, RolePermission.role_id == Role.id)
        .join(Permission, Permission.id == RolePermission.permission_id)
        .where(
            AppUser.garage_id == garage_id,
            AppUser.deleted_at.is_(None),
            Permission.code == "credit.override.manage",
        )
    )
    return [row[0] for row in result.all()]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=OverrideRequestOut,
    status_code=status.HTTP_201_CREATED,
    summary="Request a credit limit override for a customer",
)
async def create_override_request(
    user: AuthUser,
    body: OverrideRequestCreate,
    db: AsyncSession = Depends(get_db),
) -> OverrideRequestOut:
    customer = await customer_repo.get_by_public_id(db, user.garage_id, body.customer_public_id)
    if not customer:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Client introuvable.")

    if body.doc_type not in ("invoice", "delivery_note"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="doc_type invalide.")

    # Check if a pending request already exists for this specific document
    dup_stmt = select(CreditOverrideRequest).where(
        CreditOverrideRequest.garage_id == user.garage_id,
        CreditOverrideRequest.customer_id == customer.id,
        CreditOverrideRequest.doc_type == body.doc_type,
        CreditOverrideRequest.status == OverrideStatus.pending,
    )
    if body.source_document_public_id:
        dup_stmt = dup_stmt.where(
            CreditOverrideRequest.source_document_public_id == body.source_document_public_id
        )
    existing = (await db.execute(dup_stmt)).scalar_one_or_none()

    if existing:
        # Return existing pending request — no duplicate
        return OverrideRequestOut(
            id=existing.id,
            customer_id=existing.customer_id,
            customer_name=customer.full_name,
            requested_by_id=existing.requested_by_id,
            doc_type=existing.doc_type,
            status=existing.status.value,
            approved_by_id=existing.approved_by_id,
            expires_at=existing.expires_at,
            rejection_reason=existing.rejection_reason,
            created_at=existing.created_at,
        )

    req = CreditOverrideRequest(
        garage_id=user.garage_id,
        customer_id=customer.id,
        requested_by_id=user.user_id,
        doc_type=body.doc_type,
        source_document_public_id=body.source_document_public_id,
        status=OverrideStatus.pending,
    )
    db.add(req)
    await db.flush()

    # Notify all admins
    doc_label = "facture" if body.doc_type == "invoice" else "bon de livraison"
    admin_ids = await _get_admin_ids(db, user.garage_id)
    for admin_id in admin_ids:
        await create_app_notification(
            db,
            garage_id=user.garage_id,
            recipient_id=admin_id,
            title=f"Dérogation crédit demandée — {customer.full_name}",
            body=(
                f"Un utilisateur demande à créer une {doc_label} pour {customer.full_name} "
                f"dont l'encours dépasse la limite de crédit. Votre approbation est requise."
            ),
            link=f"/credit-override-requests/{req.id}",
        )

    await db.commit()
    await db.refresh(req)

    logger.info(
        "override_request_created",
        request_id=req.id,
        customer_id=customer.id,
        requested_by=user.user_id,
    )

    return OverrideRequestOut(
        id=req.id,
        customer_id=req.customer_id,
        customer_name=customer.full_name,
        requested_by_id=req.requested_by_id,
        doc_type=req.doc_type,
        status=req.status.value,
        approved_by_id=req.approved_by_id,
        expires_at=req.expires_at,
        rejection_reason=req.rejection_reason,
        created_at=req.created_at,
    )


@router.get(
    "",
    response_model=list[OverrideRequestOut],
    dependencies=[require_permission("credit.override.manage")],
    summary="List pending credit override requests (admin only)",
)
async def list_override_requests(
    user: AuthUser,
    status_filter: Optional[str] = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
) -> list[OverrideRequestOut]:
    stmt = select(CreditOverrideRequest).where(
        CreditOverrideRequest.garage_id == user.garage_id,
    )
    if status_filter:
        stmt = stmt.where(CreditOverrideRequest.status == status_filter)
    else:
        stmt = stmt.where(CreditOverrideRequest.status == OverrideStatus.pending)
    stmt = stmt.order_by(CreditOverrideRequest.created_at.desc())

    rows = (await db.execute(stmt)).scalars().all()

    out = []
    for r in rows:
        customer = await customer_repo.get_by_id(db, user.garage_id, r.customer_id)
        out.append(
            OverrideRequestOut(
                id=r.id,
                customer_id=r.customer_id,
                customer_name=customer.full_name if customer else None,
                requested_by_id=r.requested_by_id,
                doc_type=r.doc_type,
                status=r.status.value,
                approved_by_id=r.approved_by_id,
                expires_at=r.expires_at,
                rejection_reason=r.rejection_reason,
                created_at=r.created_at,
            )
        )
    return out


@router.get(
    "/{request_id}",
    response_model=OverrideRequestOut,
    dependencies=[require_permission("credit.override.manage")],
    summary="Get a single credit override request (admin only)",
)
async def get_override_request(
    request_id: int,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> OverrideRequestOut:
    req = (
        await db.execute(
            select(CreditOverrideRequest).where(
                CreditOverrideRequest.id == request_id,
                CreditOverrideRequest.garage_id == user.garage_id,
            )
        )
    ).scalar_one_or_none()
    if not req:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Demande introuvable.")

    customer = await customer_repo.get_by_id(db, user.garage_id, req.customer_id)
    return OverrideRequestOut(
        id=req.id,
        customer_id=req.customer_id,
        customer_name=customer.full_name if customer else None,
        requested_by_id=req.requested_by_id,
        doc_type=req.doc_type,
        status=req.status.value,
        approved_by_id=req.approved_by_id,
        expires_at=req.expires_at,
        rejection_reason=req.rejection_reason,
        created_at=req.created_at,
    )


@router.post(
    "/{request_id}/approve",
    response_model=OverrideRequestOut,
    dependencies=[require_permission("credit.override.manage")],
    summary="Approve a credit override request (admin only)",
)
async def approve_override(
    request_id: int,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> OverrideRequestOut:
    req = (
        await db.execute(
            select(CreditOverrideRequest).where(
                CreditOverrideRequest.id == request_id,
                CreditOverrideRequest.garage_id == user.garage_id,
            )
        )
    ).scalar_one_or_none()
    if not req:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Demande introuvable.")
    if req.status != OverrideStatus.pending:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Cette demande n'est plus en attente.")

    req.status = OverrideStatus.approved
    req.approved_by_id = user.user_id
    req.expires_at = datetime.now(tz=timezone.utc) + timedelta(hours=OVERRIDE_WINDOW_HOURS)
    await db.flush()

    # Notify the requester
    customer = await customer_repo.get_by_id(db, user.garage_id, req.customer_id)
    doc_label = "facture" if req.doc_type == "invoice" else "bon de livraison"
    await create_app_notification(
        db,
        garage_id=user.garage_id,
        recipient_id=req.requested_by_id,
        title=f"Dérogation approuvée — {customer.full_name if customer else ''}",
        body=(
            f"L'administrateur a approuvé votre demande de dérogation pour créer "
            f"une {doc_label} pour {customer.full_name if customer else 'ce client'}. "
            f"Vous avez {OVERRIDE_WINDOW_HOURS} heures pour émettre le document."
        ),
        link=f"/customers/{customer.public_id}" if customer else None,
    )

    await db.commit()
    await db.refresh(req)

    logger.info("override_approved", request_id=req.id, approved_by=user.user_id)

    return OverrideRequestOut(
        id=req.id,
        customer_id=req.customer_id,
        customer_name=customer.full_name if customer else None,
        requested_by_id=req.requested_by_id,
        doc_type=req.doc_type,
        status=req.status.value,
        approved_by_id=req.approved_by_id,
        expires_at=req.expires_at,
        rejection_reason=req.rejection_reason,
        created_at=req.created_at,
    )


@router.post(
    "/{request_id}/reject",
    response_model=OverrideRequestOut,
    dependencies=[require_permission("credit.override.manage")],
    summary="Reject a credit override request (admin only)",
)
async def reject_override(
    request_id: int,
    user: AuthUser,
    body: RejectBody,
    db: AsyncSession = Depends(get_db),
) -> OverrideRequestOut:
    req = (
        await db.execute(
            select(CreditOverrideRequest).where(
                CreditOverrideRequest.id == request_id,
                CreditOverrideRequest.garage_id == user.garage_id,
            )
        )
    ).scalar_one_or_none()
    if not req:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Demande introuvable.")
    if req.status != OverrideStatus.pending:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Cette demande n'est plus en attente.")

    req.status = OverrideStatus.rejected
    req.approved_by_id = user.user_id
    req.rejection_reason = body.reason
    await db.flush()

    # Notify the requester
    customer = await customer_repo.get_by_id(db, user.garage_id, req.customer_id)
    doc_label = "facture" if req.doc_type == "invoice" else "bon de livraison"
    reason_text = f" Motif : {body.reason}" if body.reason else ""
    await create_app_notification(
        db,
        garage_id=user.garage_id,
        recipient_id=req.requested_by_id,
        title=f"Dérogation refusée — {customer.full_name if customer else ''}",
        body=(
            f"L'administrateur a refusé votre demande de dérogation pour créer "
            f"une {doc_label} pour {customer.full_name if customer else 'ce client'}.{reason_text}"
        ),
        link=f"/customers/{customer.public_id}" if customer else None,
    )

    await db.commit()
    await db.refresh(req)

    logger.info("override_rejected", request_id=req.id, rejected_by=user.user_id)

    return OverrideRequestOut(
        id=req.id,
        customer_id=req.customer_id,
        customer_name=customer.full_name if customer else None,
        requested_by_id=req.requested_by_id,
        doc_type=req.doc_type,
        status=req.status.value,
        approved_by_id=req.approved_by_id,
        expires_at=req.expires_at,
        rejection_reason=req.rejection_reason,
        created_at=req.created_at,
    )
