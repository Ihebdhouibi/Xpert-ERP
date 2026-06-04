"""Advance payment router."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.database import get_db
from app.modules.rbac.dependencies import AuthUser, require_permission
from app.modules.advance_payment.schemas import (
    AdvancePaymentCreateRequest,
    AdvancePaymentListResponse,
    AdvancePaymentOut,
)
from app.modules.advance_payment import service
from app.core.logging import get_logger

router = APIRouter(tags=["advance-payments"])
logger = get_logger("advance_payment.router")


@router.post(
    "/advance-payments",
    status_code=status.HTTP_201_CREATED,
    response_model=AdvancePaymentOut,
    dependencies=[require_permission("deposit.record")],
)
async def record_advance_payment(
    body: AdvancePaymentCreateRequest,
    current_user: AuthUser,
    db=Depends(get_db),
):
    """Record a deposit/advance payment for a customer (before invoice exists)."""
    try:
        return await service.record_advance(
            db,
            request=body,
            garage_id=current_user.garage_id,
            user_id=current_user.user_id,
        )
    except service.CustomerNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")


@router.get(
    "/advance-payments/customers/{customer_id}",
    response_model=AdvancePaymentListResponse,
    dependencies=[require_permission("invoice.read")],
)
async def list_customer_advances(
    customer_id: int,
    current_user: AuthUser,
    db=Depends(get_db),
):
    """List all advance payments (applied + pending) for a customer."""
    return await service.list_advances(
        db,
        customer_id=customer_id,
        garage_id=current_user.garage_id,
    )
