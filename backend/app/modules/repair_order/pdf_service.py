"""PDF report generation for repair orders using WeasyPrint + Jinja2."""
from __future__ import annotations

import asyncio
import functools
import os
import uuid as uuid_lib
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings
from app.modules.customer.models import Customer
from app.modules.repair_order.models import RepairOrder
from app.modules.vehicles.models import Vehicle


STATUS_LABELS_FR = {
    "created": "Créé",
    "diagnosis": "Diagnostic",
    "in_repair": "En réparation",
    "finished": "Terminé",
    "delivered": "Livré",
    "paused_parts": "En attente de pièces",
    "paused_approval": "En attente d'approbation",
}

_TEMPLATE_DIR = Path(__file__).parent
_jinja_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=select_autoescape(["html"]),
)


def _money(minor: Optional[int], currency: str) -> str:
    if minor is None:
        return "—"
    value = minor / 100
    return f"{value:,.2f}".replace(",", " ")


def _render_html(
    ro: RepairOrder,
    customer: Optional[Customer],
    vehicle: Optional[Vehicle],
    mechanic_name: str,
    settings: Settings,
) -> str:
    currency = ro.estimated_cost_currency or "DT"
    labor_total_minor = sum(l.amount_minor for l in ro.labor_lines)
    parts_total_minor = sum(p.amount_minor for p in ro.part_lines)

    template = _jinja_env.get_template("pdf_template.html")
    return template.render(
        ro=ro,
        customer=customer,
        vehicle=vehicle,
        cfg=settings,
        status_label=STATUS_LABELS_FR.get(ro.status.value, ro.status.value),
        currency=currency,
        estimated_cost=_money(ro.estimated_cost_minor, currency),
        actual_cost=_money(ro.actual_cost_minor, currency),
        labor_total=_money(labor_total_minor, currency),
        parts_total=_money(parts_total_minor, currency),
        grand_total=_money(ro.actual_cost_minor, currency),
        mechanic_name=mechanic_name,
    )


def _generate_pdf_sync(html: str, gtk3_dll_dir: str) -> bytes:
    """Synchronous WeasyPrint call — run in executor to avoid blocking the loop."""
    if gtk3_dll_dir and os.name == "nt":
        os.add_dll_directory(gtk3_dll_dir)
    import weasyprint  # import after DLL directory is registered
    return weasyprint.HTML(string=html).write_pdf()


async def generate_pdf(
    db: AsyncSession,
    ro: RepairOrder,
    settings: Settings,
) -> bytes:
    """Fetch related data, render the template, and produce PDF bytes."""
    # Ensure labor/part lines are loaded
    if not hasattr(ro, "_sa_instance_state") or ro.labor_lines is None:
        result = await db.execute(
            select(RepairOrder)
            .where(RepairOrder.id == ro.id)
            .options(
                selectinload(RepairOrder.labor_lines),
                selectinload(RepairOrder.part_lines),
                selectinload(RepairOrder.status_events),
            )
        )
        ro = result.scalar_one()

    # Fetch customer
    customer: Optional[Customer] = None
    if ro.customer_id:
        result = await db.execute(
            select(Customer).where(Customer.id == ro.customer_id)
        )
        customer = result.scalar_one_or_none()

    # Fetch vehicle
    vehicle: Optional[Vehicle] = None
    if ro.vehicle_id:
        result = await db.execute(
            select(Vehicle).where(Vehicle.id == ro.vehicle_id)
        )
        vehicle = result.scalar_one_or_none()

    # Resolve mechanic name
    mechanic_name = "—"
    if ro.assigned_user_id:
        from app.modules.auth.models import AppUser
        result = await db.execute(
            select(AppUser.full_name).where(AppUser.id == ro.assigned_user_id)
        )
        row = result.first()
        if row:
            mechanic_name = row[0]

    html = _render_html(ro, customer, vehicle, mechanic_name, settings)

    gtk3_dir = settings.cfg_gtk3_dll_dir
    loop = asyncio.get_running_loop()
    pdf_bytes: bytes = await loop.run_in_executor(
        None, functools.partial(_generate_pdf_sync, html, gtk3_dir)
    )
    return pdf_bytes


async def upload_pdf_and_sign(
    pdf_bytes: bytes,
    ro: RepairOrder,
    settings: Settings,
) -> str:
    """Upload PDF to S3 and return a presigned download URL."""
    from app.modules.documents.storage import generate_presigned_url, upload_bytes

    key = f"repair-orders/{ro.id}/reports/{uuid_lib.uuid4()}.pdf"
    await upload_bytes(
        bucket=settings.s3_bucket_documents,
        key=key,
        data=pdf_bytes,
        content_type="application/pdf",
    )
    url = await generate_presigned_url(
        bucket=settings.s3_bucket_documents,
        key=key,
        expiry_seconds=settings.signed_url_expiry_seconds,
    )
    return url
