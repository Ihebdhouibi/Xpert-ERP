"""Payment router."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.rbac.dependencies import AuthUser, require_permission
from app.modules.payment import service as pay_svc
from app.modules.payment.schemas import PaymentCreateRequest, PaymentOut
from app.modules.payment.service import InvoiceNotPayableError, OverpaymentError, PaymentError
from app.core.logging import get_logger

router = APIRouter(prefix="/payments", tags=["payments"])
logger = get_logger("payment.router")


@router.post(
    "",
    response_model=PaymentOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[require_permission("payment.record")],
)
async def record_payment(
    request: PaymentCreateRequest,
    current_user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> PaymentOut:
    try:
        return await pay_svc.record_payment(
            db,
            request=request,
            garage_id=current_user.garage_id,
            user_id=current_user.user_id,
        )
    except InvoiceNotPayableError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except OverpaymentError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except PaymentError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get(
    "/invoices/{invoice_id}",
    response_model=List[PaymentOut],
    dependencies=[require_permission("invoice.read")],
)
async def list_invoice_payments(
    invoice_id: int,
    current_user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> List[PaymentOut]:
    try:
        return list(
            await pay_svc.list_payments(
                db,
                invoice_id=invoice_id,
                garage_id=current_user.garage_id,
            )
        )
    except PaymentError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
