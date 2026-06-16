"""PDF download router.

GET /pdf/credit-notes/{id}     — requires credit_note.read
GET /pdf/quotations/{id}       — requires quotation.read
GET /pdf/invoices/{id}         — requires invoice.read
GET /pdf/delivery-notes/{id}   — requires invoice.read
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.pdf import service as pdf_service
from app.modules.rbac.dependencies import AuthUser, require_permission
from app.core.logging import get_logger

router = APIRouter(prefix="/pdf", tags=["pdf"])
logger = get_logger("pdf.router")


@router.get(
    "/purchase-orders/{public_id}",
    response_class=Response,
    responses={
        200: {"content": {"application/pdf": {}}, "description": "PDF document"},
        404: {"description": "Purchase order not found"},
    },
    dependencies=[require_permission("purchase_order.read")],
)
async def download_purchase_order_pdf(
    public_id: str,
    current_user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> Response:
    try:
        pdf_bytes = await pdf_service.render_purchase_order_pdf(
            db, public_id=public_id, garage_id=current_user.garage_id
        )
    except ValueError:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Purchase order not found")

    filename = f"bon-commande-{public_id[:8]}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/supplier-invoices/{public_id}",
    response_class=Response,
    responses={
        200: {"content": {"application/pdf": {}}, "description": "PDF document"},
        404: {"description": "Supplier invoice not found"},
    },
    dependencies=[require_permission("supplier_invoice.read")],
)
async def download_supplier_invoice_pdf(
    public_id: str,
    current_user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> Response:
    try:
        pdf_bytes = await pdf_service.render_supplier_invoice_pdf(
            db, public_id=public_id, garage_id=current_user.garage_id
        )
    except ValueError:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Supplier invoice not found")

    filename = f"facture-fournisseur-{public_id[:8]}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/credit-notes/{credit_note_id}",
    response_class=Response,
    responses={
        200: {"content": {"application/pdf": {}}, "description": "PDF document"},
        404: {"description": "Credit note not found"},
    },
    dependencies=[require_permission("credit_note.read")],
)
async def download_credit_note_pdf(
    credit_note_id: int,
    current_user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> Response:
    try:
        pdf_bytes = await pdf_service.render_credit_note_pdf(
            db, credit_note_id=credit_note_id, garage_id=current_user.garage_id
        )
    except ValueError:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Credit note not found")

    filename = f"avoir-{credit_note_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@router.get(
    "/quotations/{quotation_id}",
    response_class=Response,
    responses={
        200: {"content": {"application/pdf": {}}, "description": "PDF document"},
        404: {"description": "Quotation not found"},
    },
    dependencies=[require_permission("quotation.read")],
)
async def download_quotation_pdf(
    quotation_id: int,
    current_user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> Response:
    try:
        pdf_bytes = await pdf_service.render_quotation_pdf(
            db, quotation_id=quotation_id, garage_id=current_user.garage_id
        )
    except ValueError:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Quotation not found")

    filename = f"devis-{quotation_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/invoices/{invoice_id}",
    response_class=Response,
    responses={
        200: {"content": {"application/pdf": {}}, "description": "PDF document"},
        404: {"description": "Invoice not found"},
    },
    dependencies=[require_permission("invoice.read")],
)
async def download_invoice_pdf(
    invoice_id: int,
    current_user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> Response:
    try:
        pdf_bytes = await pdf_service.render_invoice_pdf(
            db, invoice_id=invoice_id, garage_id=current_user.garage_id
        )
    except ValueError:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Invoice not found")

    filename = f"facture-{invoice_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/delivery-notes/{delivery_note_id}",
    response_class=Response,
    responses={
        200: {"content": {"application/pdf": {}}, "description": "PDF document"},
        404: {"description": "Delivery note not found"},
    },
    dependencies=[require_permission("invoice.read")],
)
async def download_delivery_note_pdf(
    delivery_note_id: int,
    current_user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> Response:
    try:
        pdf_bytes = await pdf_service.render_delivery_note_pdf(
            db, delivery_note_id=delivery_note_id, garage_id=current_user.garage_id
        )
    except ValueError:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Delivery note not found")

    filename = f"bon-livraison-{delivery_note_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
