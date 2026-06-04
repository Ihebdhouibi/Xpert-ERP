"""Cash session service — open, close, Z-report."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, func as sqlfunc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.modules.cash_session import repository as repo
from app.modules.cash_session.models import CashSession, CashSessionStatus
from app.modules.cash_session.schemas import (
    CashSessionListResponse,
    CashSessionOut,
    PaymentMethodTally,
    ZReportData,
)
from app.modules.payment.models import Payment, PaymentMethod

logger = get_logger("cash_session.service")


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class SessionAlreadyOpenError(Exception):
    pass


class SessionNotFoundError(Exception):
    pass


class SessionAlreadyClosedError(Exception):
    pass


class ClosingReasonRequiredError(Exception):
    pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _compute_tallies(
    db: AsyncSession, session_id: int
) -> tuple[list[PaymentMethodTally], int]:
    """Aggregate payments by method for a given session."""
    result = await db.execute(
        select(
            Payment.payment_method,
            sqlfunc.count(Payment.id).label("cnt"),
            sqlfunc.coalesce(sqlfunc.sum(Payment.amount_minor), 0).label("total"),
        )
        .where(Payment.cash_session_id == session_id)
        .group_by(Payment.payment_method)
    )
    rows = result.all()

    tallies = [
        PaymentMethodTally(
            payment_method=row.payment_method,
            count=row.cnt,
            total_minor=row.total,
        )
        for row in rows
    ]
    total_all = sum(t.total_minor for t in tallies)
    return tallies, total_all


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


async def open_session(
    db: AsyncSession,
    *,
    garage_id: int,
    user_id: int,
) -> CashSessionOut:
    logger.info("open_session_start", garage_id=garage_id, user_id=user_id)
    existing = await repo.get_open_session(db, garage_id)
    if existing:
        raise SessionAlreadyOpenError(
            f"A cash session is already open (id={existing.id})."
        )

    session = CashSession(
        garage_id=garage_id,
        status=CashSessionStatus.open,
        opened_at=datetime.now(tz=timezone.utc),
        opened_by_id=user_id,
    )
    await repo.create(db, session)
    await db.commit()

    fresh = await repo.get_by_id(db, session.id, garage_id)
    logger.info("cash_session_opened", session_id=session.id, garage_id=garage_id)
    return CashSessionOut.model_validate(fresh)


async def close_session(
    db: AsyncSession,
    *,
    session_id: int,
    garage_id: int,
    user_id: int,
    counted_total_cash: int,
    closing_reason: Optional[str] = None,
) -> CashSessionOut:
    logger.info("close_session_start", session_id=session_id, garage_id=garage_id, user_id=user_id)
    settings = get_settings()
    session = await repo.get_by_id(db, session_id, garage_id)
    if not session:
        raise SessionNotFoundError(session_id)
    if session.status == CashSessionStatus.closed:
        raise SessionAlreadyClosedError(session_id)

    # Compute expected cash from payments in this session (cash method only)
    result = await db.execute(
        select(sqlfunc.coalesce(sqlfunc.sum(Payment.amount_minor), 0)).where(
            Payment.cash_session_id == session_id,
            Payment.payment_method == PaymentMethod.cash,
        )
    )
    expected = result.scalar_one()

    difference = counted_total_cash - expected

    if difference != 0 and settings.cash_diff_require_reason and not closing_reason:
        raise ClosingReasonRequiredError(
            f"A closing reason is required when the difference is non-zero (difference={difference})."
        )

    session.status = CashSessionStatus.closed
    session.closed_at = datetime.now(tz=timezone.utc)
    session.closed_by_id = user_id
    session.expected_total_cash = expected
    session.counted_total_cash = counted_total_cash
    session.difference = difference
    session.closing_reason = closing_reason

    await repo.save(db, session)
    await db.commit()

    fresh = await repo.get_by_id(db, session_id, garage_id)
    logger.info(
        "cash_session_closed",
        session_id=session_id,
        difference=difference,
        garage_id=garage_id,
    )
    return CashSessionOut.model_validate(fresh)


async def get_session(
    db: AsyncSession, session_id: int, garage_id: int
) -> CashSessionOut:
    logger.info("get_session_start", session_id=session_id, garage_id=garage_id)
    session = await repo.get_by_id(db, session_id, garage_id)
    if not session:
        raise SessionNotFoundError(session_id)
    return CashSessionOut.model_validate(session)


async def get_current_open_session(
    db: AsyncSession, garage_id: int
) -> Optional[CashSessionOut]:
    logger.info("get_current_open_session_start", garage_id=garage_id)
    session = await repo.get_open_session(db, garage_id)
    if not session:
        return None
    return CashSessionOut.model_validate(session)


async def list_sessions(
    db: AsyncSession,
    garage_id: int,
    *,
    page: int = 1,
    page_size: int = 25,
) -> CashSessionListResponse:
    logger.info("list_sessions_start", garage_id=garage_id, page=page)
    items, total = await repo.list_by_garage(db, garage_id, page=page, page_size=page_size)
    return CashSessionListResponse(
        items=[CashSessionOut.model_validate(s) for s in items],
        total=total,
        page=page,
        page_size=page_size,
    )


async def get_z_report_data(
    db: AsyncSession, session_id: int, garage_id: int
) -> ZReportData:
    logger.info("get_z_report_data_start", session_id=session_id, garage_id=garage_id)
    session = await repo.get_by_id(db, session_id, garage_id)
    if not session:
        raise SessionNotFoundError(session_id)

    tallies, total_all = await _compute_tallies(db, session_id)

    return ZReportData(
        session_id=session.id,
        garage_id=session.garage_id,
        opened_at=session.opened_at,
        closed_at=session.closed_at,
        opened_by_id=session.opened_by_id,
        closed_by_id=session.closed_by_id,
        tallies=tallies,
        expected_total_cash=session.expected_total_cash,
        counted_total_cash=session.counted_total_cash,
        difference=session.difference,
        closing_reason=session.closing_reason,
        total_all_methods=total_all,
    )


async def generate_z_report_pdf(
    db: AsyncSession, session_id: int, garage_id: int
) -> bytes:
    """Render Z-report as PDF bytes using WeasyPrint."""
    logger.info("generate_z_report_pdf_start", session_id=session_id, garage_id=garage_id)
    from app.core.config import get_settings
    from jinja2 import Environment, FileSystemLoader
    from pathlib import Path
    import weasyprint

    data = await get_z_report_data(db, session_id, garage_id)
    settings = get_settings()

    template_dir = Path(__file__).parent.parent.parent.parent / "templates" / "documents"
    env = Environment(loader=FileSystemLoader(str(template_dir)), autoescape=True)
    template = env.get_template("z_report.html")

    html_str = template.render(
        data=data,
        cfg=settings,
    )

    loop = asyncio.get_event_loop()
    pdf_bytes = await loop.run_in_executor(
        None,
        lambda: weasyprint.HTML(string=html_str).write_pdf(),
    )
    return pdf_bytes
