"""Customer credit-limit enforcement and balance-ledger helpers.

Design
------
* The `customer_balance_event` table is append-only (never update/delete).
* `customer.outstanding_minor` is a denormalised snapshot kept in sync on
  every write for fast list-view queries.
* `delta_minor` semantics:
    +N  →  customer owes more  (invoice issued)
    -N  →  customer owes less  (payment received, credit note, cancellation)
* Credit limit is enforced at invoice-issue time only (not on quotation
  creation) because amounts can still change while in draft.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, func as sqlfunc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.modules.customer.models import Customer, CustomerBalanceEvent
from app.modules.customer import repository as customer_repo
from app.core.logging import get_logger

logger = get_logger("customer.credit")


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class CreditLimitExceededError(Exception):
    """Raised in 'block' mode when posting would exceed the customer's credit limit."""

    def __init__(self, customer_id: int, limit: int, outstanding: int, additional: int) -> None:
        self.customer_id = customer_id
        self.limit = limit
        self.outstanding = outstanding
        self.additional = additional
        super().__init__(
            f"Customer {customer_id}: credit limit {limit} would be exceeded "
            f"(outstanding={outstanding}, additional={additional})."
        )


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------


async def post_balance_event(
    db: AsyncSession,
    *,
    customer_id: int,
    garage_id: int,
    reason: str,
    delta_minor: int,
    currency: str,
    ref_type: Optional[str] = None,
    ref_id: Optional[int] = None,
    created_by: Optional[int] = None,
) -> CustomerBalanceEvent:
    """Append a balance event row and update customer.outstanding_minor.

    The caller is responsible for calling ``await db.commit()`` afterwards.
    """
    event = CustomerBalanceEvent(
        customer_id=customer_id,
        reason=reason,
        delta_minor=delta_minor,
        currency=currency,
        ref_type=ref_type,
        ref_id=ref_id,
        occurred_at=datetime.now(tz=timezone.utc),
        created_by_user_id=created_by,
    )
    db.add(event)
    await db.flush()

    # Update the denormalised snapshot on customer row
    customer = await customer_repo.get_by_id(db, garage_id, customer_id)
    if customer:
        customer.outstanding_minor = (customer.outstanding_minor or 0) + delta_minor
        db.add(customer)
        await db.flush()

    logger.info(
        "balance_event_posted",
        customer_id=customer_id,
        reason=reason,
        delta_minor=delta_minor,
    )
    return event


async def check_credit_limit(
    db: AsyncSession,
    *,
    customer_id: int,
    garage_id: int,
    additional_amount_minor: int,
) -> None:
    """Check if posting `additional_amount_minor` would exceed the credit limit.

    * If `credit_limit_minor == 0`  → no limit set, always passes.
    * mode='block'                  → raises CreditLimitExceededError.
    * mode='warn'                   → logs a warning and continues.
    """
    settings = get_settings()
    customer = await customer_repo.get_by_id(db, garage_id, customer_id)
    if not customer or customer.credit_limit_minor == 0:
        return  # no limit configured

    projected = (customer.outstanding_minor or 0) + additional_amount_minor
    if projected <= customer.credit_limit_minor:
        return  # within limit

    if settings.credit_limit_mode == "block":
        raise CreditLimitExceededError(
            customer_id=customer_id,
            limit=customer.credit_limit_minor,
            outstanding=customer.outstanding_minor or 0,
            additional=additional_amount_minor,
        )
    else:
        logger.warning(
            "credit_limit_exceeded_warn",
            customer_id=customer_id,
            limit=customer.credit_limit_minor,
            outstanding=customer.outstanding_minor or 0,
            additional=additional_amount_minor,
        )


async def recompute_outstanding(
    db: AsyncSession,
    *,
    customer_id: int,
    garage_id: int,
) -> int:
    """Recompute outstanding_minor from ledger SUM and persist it.

    Use for reconciliation; not called on the hot path.
    """
    result = await db.execute(
        select(sqlfunc.coalesce(sqlfunc.sum(CustomerBalanceEvent.delta_minor), 0)).where(
            CustomerBalanceEvent.customer_id == customer_id
        )
    )
    total = result.scalar_one()

    customer = await customer_repo.get_by_id(db, garage_id, customer_id)
    if customer:
        customer.outstanding_minor = total
        db.add(customer)
        await db.flush()

    return total
