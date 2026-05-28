"""PDF report generation for inspection diagnostics using WeasyPrint + Jinja2."""
from __future__ import annotations

import asyncio
import functools
import os
from pathlib import Path
from typing import Any, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings
from app.modules.inspection.models import Inspection


_ITEM_STATUS_LABELS: dict[str, str] = {
    "ok": "OK",
    "attention": "À surveiller",
    "defective": "Défectueux",
    "not_applicable": "N/A",
}

_ITEM_STATUS_COLORS: dict[str, str] = {
    "ok": "#22c55e",
    "attention": "#f59e0b",
    "defective": "#ef4444",
    "not_applicable": "#9ca3af",
}

_TEMPLATE_DIR = Path(__file__).parent
_jinja_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=select_autoescape(["html"]),
)


def _build_sections(inspection: Inspection) -> list[dict]:
    results_map = {r.item_id: r for r in inspection.results}
    sections = []
    for section in (inspection.template.sections or []):
        items = []
        for item in section.get("items", []):
            result = results_map.get(item["id"])
            status = result.status.value if result else None
            items.append(
                {
                    "id": item["id"],
                    "label": item["label"],
                    "status": status,
                    "status_label": _ITEM_STATUS_LABELS.get(status or "", "—"),
                    "status_color": _ITEM_STATUS_COLORS.get(status or "", "#9ca3af"),
                    "notes": result.notes if result else None,
                }
            )
        done = sum(1 for i in items if i["status"])
        issues = sum(1 for i in items if i["status"] in ("attention", "defective"))
        sections.append(
            {
                "title": section.get("title", ""),
                "items": items,
                "done": done,
                "total": len(items),
                "issues": issues,
            }
        )
    return sections


def _render_html(
    inspection: Inspection,
    vehicle: Any,
    mechanic_name: str,
    settings: Settings,
) -> str:
    sections = _build_sections(inspection)
    total_items = sum(s["total"] for s in sections)
    total_done = sum(s["done"] for s in sections)
    total_issues = sum(s["issues"] for s in sections)
    template = _jinja_env.get_template("inspection_pdf_template.html")
    return template.render(
        inspection=inspection,
        vehicle=vehicle,
        mechanic_name=mechanic_name,
        sections=sections,
        total_items=total_items,
        total_done=total_done,
        total_issues=total_issues,
        cfg=settings,
    )


def _generate_pdf_sync(html: str, gtk3_dll_dir: str) -> bytes:
    if gtk3_dll_dir and os.name == "nt":
        os.add_dll_directory(gtk3_dll_dir)
    import weasyprint  # import after DLL directory is registered
    return weasyprint.HTML(string=html).write_pdf()


async def generate_pdf(
    db: AsyncSession,
    inspection: Inspection,
    settings: Settings,
) -> bytes:
    result = await db.execute(
        select(Inspection)
        .where(Inspection.id == inspection.id)
        .options(
            selectinload(Inspection.results),
            selectinload(Inspection.template),
        )
    )
    inspection = result.scalar_one()

    vehicle: Optional[Any] = None
    if inspection.vehicle_id:
        from app.modules.vehicles.models import Vehicle
        vrow = await db.execute(select(Vehicle).where(Vehicle.id == inspection.vehicle_id))
        vehicle = vrow.scalar_one_or_none()

    mechanic_name = "—"
    if inspection.mechanic_id:
        from app.modules.auth.models import AppUser
        mrow = await db.execute(
            select(AppUser.full_name).where(AppUser.id == inspection.mechanic_id)
        )
        row = mrow.first()
        if row:
            mechanic_name = row[0]

    html = _render_html(inspection, vehicle, mechanic_name, settings)
    gtk3_dir = settings.cfg_gtk3_dll_dir
    loop = asyncio.get_running_loop()
    pdf_bytes: bytes = await loop.run_in_executor(
        None, functools.partial(_generate_pdf_sync, html, gtk3_dir)
    )
    return pdf_bytes
