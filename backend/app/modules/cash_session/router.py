"""Cash session router."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.core.database import get_db
from app.modules.rbac.dependencies import AuthUser, require_permission
from app.modules.cash_session.schemas import (
    CashSessionListResponse,
    CashSessionOut,
    CloseSessionRequest,
    ZReportData,
)
from app.modules.cash_session import service

router = APIRouter(tags=["cash-sessions"])


@router.post(
    "/cash-sessions",
    status_code=status.HTTP_201_CREATED,
    response_model=CashSessionOut,
    dependencies=[require_permission("cash_session.open")],
)
async def open_cash_session(
    current_user: AuthUser,
    db=Depends(get_db),
):
    """Open a new cash session. Only one session may be open per garage at a time."""
    try:
        return await service.open_session(
            db,
            garage_id=current_user.garage_id,
            user_id=current_user.user_id,
        )
    except service.SessionAlreadyOpenError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.post(
    "/cash-sessions/{session_id}/close",
    response_model=CashSessionOut,
    dependencies=[require_permission("cash_session.close")],
)
async def close_cash_session(
    session_id: int,
    body: CloseSessionRequest,
    current_user: AuthUser,
    db=Depends(get_db),
):
    """Close a cash session, record the physical cash count, and compute the difference."""
    try:
        return await service.close_session(
            db,
            session_id=session_id,
            garage_id=current_user.garage_id,
            user_id=current_user.user_id,
            counted_total_cash=body.counted_total_cash,
            closing_reason=body.closing_reason,
        )
    except service.SessionNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")
    except service.SessionAlreadyClosedError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Session is already closed.")
    except service.ClosingReasonRequiredError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


@router.get(
    "/cash-sessions/current",
    response_model=CashSessionOut | None,
    dependencies=[require_permission("cash_session.read")],
)
async def get_current_session(
    current_user: AuthUser,
    db=Depends(get_db),
):
    """Return the current open cash session, or null if none is open."""
    return await service.get_current_open_session(db, current_user.garage_id)


@router.get(
    "/cash-sessions",
    response_model=CashSessionListResponse,
    dependencies=[require_permission("cash_session.read")],
)
async def list_cash_sessions(
    current_user: AuthUser,
    db=Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
):
    """List all cash sessions for the garage, newest first."""
    return await service.list_sessions(
        db, current_user.garage_id, page=page, page_size=page_size
    )


@router.get(
    "/cash-sessions/{session_id}",
    response_model=CashSessionOut,
    dependencies=[require_permission("cash_session.read")],
)
async def get_cash_session(
    session_id: int,
    current_user: AuthUser,
    db=Depends(get_db),
):
    try:
        return await service.get_session(db, session_id, current_user.garage_id)
    except service.SessionNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")


@router.get(
    "/cash-sessions/{session_id}/z-report",
    response_model=ZReportData,
    dependencies=[require_permission("cash_session.read")],
)
async def get_z_report(
    session_id: int,
    current_user: AuthUser,
    db=Depends(get_db),
):
    """Get Z-report data (JSON) for a session."""
    try:
        return await service.get_z_report_data(db, session_id, current_user.garage_id)
    except service.SessionNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")


@router.get(
    "/cash-sessions/{session_id}/z-report/pdf",
    dependencies=[require_permission("cash_session.read")],
)
async def get_z_report_pdf(
    session_id: int,
    current_user: AuthUser,
    db=Depends(get_db),
):
    """Generate and return Z-report PDF for a session."""
    try:
        pdf_bytes = await service.generate_z_report_pdf(
            db, session_id, current_user.garage_id
        )
    except service.SessionNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename=z_report_{session_id}.pdf"},
    )
