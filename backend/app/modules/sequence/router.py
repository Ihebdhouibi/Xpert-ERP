"""Document sequence router — admin inspection endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.rbac.dependencies import AuthUser, require_permission
from app.modules.sequence import service
from app.modules.sequence.schemas import SequenceStateOut
from app.core.logging import get_logger

router = APIRouter(prefix="/sequences", tags=["sequences"])
logger = get_logger("sequence.router")


@router.get(
    "",
    response_model=list[SequenceStateOut],
    dependencies=[require_permission("admin.sequence.read")],
    summary="List current document sequence counters for the caller's garage",
)
async def list_sequences(
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> list[SequenceStateOut]:
    """Read-only admin view — returns current `last_number` per doc type per year."""
    return await service.peek(db, garage_id=user.garage_id)
