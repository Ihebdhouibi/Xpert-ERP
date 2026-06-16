"""Bon de Retour repository — all DB queries."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.bon_de_retour.models import (
    BonDeRetour,
    BonDeRetourLine,
    BonDeRetourPartyType,
    BonDeRetourStatus,
    SupplierCreditNote,
    SupplierCreditNoteStatus,
)


async def create(db: AsyncSession, bdr: BonDeRetour) -> BonDeRetour:
    db.add(bdr)
    await db.flush()
    await db.refresh(bdr)
    return bdr


async def get_by_id(db: AsyncSession, bdr_id: int, garage_id: int) -> Optional[BonDeRetour]:
    result = await db.execute(
        select(BonDeRetour)
        .where(
            BonDeRetour.id == bdr_id,
            BonDeRetour.garage_id == garage_id,
            BonDeRetour.deleted_at.is_(None),
        )
        .options(selectinload(BonDeRetour.lines))
    )
    return result.scalar_one_or_none()


async def get_by_public_id(db: AsyncSession, public_id: str, garage_id: int) -> Optional[BonDeRetour]:
    result = await db.execute(
        select(BonDeRetour)
        .where(
            BonDeRetour.public_id == public_id,
            BonDeRetour.garage_id == garage_id,
            BonDeRetour.deleted_at.is_(None),
        )
        .options(selectinload(BonDeRetour.lines))
    )
    return result.scalar_one_or_none()


async def list_bon_de_retour(
    db: AsyncSession,
    garage_id: int,
    *,
    party_type: Optional[BonDeRetourPartyType] = None,
    status: Optional[BonDeRetourStatus] = None,
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[BonDeRetour], int]:
    base = select(BonDeRetour).where(
        BonDeRetour.garage_id == garage_id, BonDeRetour.deleted_at.is_(None)
    )
    if party_type is not None:
        base = base.where(BonDeRetour.party_type == party_type)
    if status is not None:
        base = base.where(BonDeRetour.status == status)

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = await db.execute(
        base.options(selectinload(BonDeRetour.lines))
        .order_by(BonDeRetour.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(rows.scalars().all()), total


async def save(db: AsyncSession, bdr: BonDeRetour) -> BonDeRetour:
    await db.flush()
    return bdr


async def soft_delete(db: AsyncSession, bdr: BonDeRetour, deleted_by: int) -> None:
    bdr.deleted_at = datetime.now(tz=timezone.utc)
    bdr.updated_by = deleted_by
    await db.flush()


async def get_line(db: AsyncSession, line_id: int, bon_de_retour_id: int) -> Optional[BonDeRetourLine]:
    result = await db.execute(
        select(BonDeRetourLine).where(
            BonDeRetourLine.id == line_id,
            BonDeRetourLine.bon_de_retour_id == bon_de_retour_id,
        )
    )
    return result.scalar_one_or_none()


async def delete_line(db: AsyncSession, line: BonDeRetourLine) -> None:
    await db.delete(line)
    await db.flush()


# ---------------------------------------------------------------------------
# Supplier credit note (avoir fournisseur)
# ---------------------------------------------------------------------------

async def create_supplier_credit_note(db: AsyncSession, scn: SupplierCreditNote) -> SupplierCreditNote:
    db.add(scn)
    await db.flush()
    await db.refresh(scn)
    return scn


async def get_supplier_credit_note_by_id(
    db: AsyncSession, scn_id: int, garage_id: int
) -> Optional[SupplierCreditNote]:
    result = await db.execute(
        select(SupplierCreditNote).where(
            SupplierCreditNote.id == scn_id, SupplierCreditNote.garage_id == garage_id
        )
    )
    return result.scalar_one_or_none()


async def list_supplier_credit_notes(
    db: AsyncSession,
    garage_id: int,
    *,
    status: Optional[SupplierCreditNoteStatus] = None,
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[SupplierCreditNote], int]:
    base = select(SupplierCreditNote).where(SupplierCreditNote.garage_id == garage_id)
    if status is not None:
        base = base.where(SupplierCreditNote.status == status)

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = await db.execute(
        base.order_by(SupplierCreditNote.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(rows.scalars().all()), total
