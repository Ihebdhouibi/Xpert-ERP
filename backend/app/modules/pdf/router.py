"""PDF download router.

GET /pdf/quotations/{id}  — requires quotation.read
GET /pdf/invoices/{id}    — requires invoice.read
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
