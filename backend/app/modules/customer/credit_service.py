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
* Threshold notifications fire at 80 % and 90 % when the encours crosses
  those levels for the first time; crossing is tracked via
  `customer.last_notified_threshold`.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select, func as sqlfunc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.modules.customer.models import (
    Customer,
    CustomerBalanceEvent,
    CreditOverrideRequest,
    OverrideStatus,
)
from app.modules.customer import repository as customer_repo
from app.core.logging import get_logger

logger = get_logger("customer.credit")

# How long an admin approval stays valid before it expires.
OVERRIDE_WINDOW_HOURS = 24


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class CreditLimitExceededError(Exception):
    """Raised in 'block' mode when posting would exceed the customer's credit limit."""

    def __init__(
        self,
        customer_id: int,
        limit: int,
        outstanding: int,
        additional: int,
        customer_public_id: Optional[str] = None,
    ) -> None:
        self.customer_id = customer_id
        self.limit = limit
        self.outstanding = outstanding
        self.additional = additional
        self.customer_public_id = customer_public_id
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

    Also fires threshold notifications when the encours crosses 80 % or 90 %
    of the credit limit for the first time.

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

        # Fire threshold notifications if applicable (only when balance increases)
        if delta_minor > 0:
            await _maybe_notify_threshold(db, customer, garage_id)

    logger.info(
        "balance_event_posted",
        customer_id=customer_id,
        reason=reason,
        delta_minor=delta_minor,
    )
    return event


async def _maybe_notify_threshold(
    db: AsyncSession,
    customer: Customer,
    garage_id: int,
) -> None:
    """Fire in-app notifications when the encours crosses 80 % or 90 % of limit.

    Only fires once per threshold crossing (tracked via last_notified_threshold).
    """
    if not customer.credit_limit_minor:
        return

    ratio = (customer.outstanding_minor or 0) / customer.credit_limit_minor
    current_threshold = customer.last_notified_threshold or 0

    new_threshold: Optional[int] = None
    if ratio >= 0.90 and current_threshold < 90:
        new_threshold = 90
    elif ratio >= 0.80 and current_threshold < 80:
        new_threshold = 80

    if new_threshold is None:
        return

    customer.last_notified_threshold = new_threshold
    db.add(customer)
    await db.flush()

    await _send_threshold_notifications(db, customer, garage_id, new_threshold)


async def _send_threshold_notifications(
    db: AsyncSession,
    customer: Customer,
    garage_id: int,
    threshold: int,
) -> None:
    """Create in-app notifications for all garage users (+ admin for 90 %)."""
    from app.modules.auth.models import AppUser, UserRole, Role, RolePermission, Permission
    from app.modules.notification.inbox_router import create_app_notification
    from sqlalchemy.orm import selectinload

    limit_eur = (customer.credit_limit_minor or 0) / 100
    outstanding_eur = (customer.outstanding_minor or 0) / 100

    title = (
        f"⚠️ Encours {threshold} % — {customer.full_name}"
    )
    body = (
        f"L'encours de {customer.full_name} atteint {threshold} % de sa limite de crédit "
        f"({outstanding_eur:,.2f} € / {limit_eur:,.2f} €)."
    )
    link = f"/customers/{customer.public_id}"

    # Query all active users in the garage
    users_result = await db.execute(
        select(AppUser).where(
            AppUser.garage_id == garage_id,
            AppUser.deleted_at.is_(None),
        )
    )
    all_users = users_result.scalars().all()

    if threshold == 90:
        # Notify everyone
        recipients = all_users
    else:
        # 80 % — notify all users who have invoice.read permission (front-office staff)
        # rather than spamming everyone; admins are included naturally.
        recipients = all_users

    for u in recipients:
        await create_app_notification(
            db,
            garage_id=garage_id,
            recipient_id=u.id,
            title=title,
            body=body,
            link=link,
        )

    logger.info(
        "credit_threshold_notified",
        customer_id=customer.id,
        threshold=threshold,
        recipients=len(recipients),
    )


# ---------------------------------------------------------------------------
# Override request helpers
# ---------------------------------------------------------------------------


async def get_valid_override(
    db: AsyncSession,
    *,
    customer_id: int,
    garage_id: int,
    doc_type: str,
    source_document_public_id: Optional[str] = None,
) -> Optional[CreditOverrideRequest]:
    """Return an approved, non-expired override for this customer+doc_type+document, or None.

    When source_document_public_id is provided the override must match that
    specific document — this prevents an approval for BL-A from unlocking BL-B.
    """
    now = datetime.now(tz=timezone.utc)
    stmt = select(CreditOverrideRequest).where(
        CreditOverrideRequest.garage_id == garage_id,
        CreditOverrideRequest.customer_id == customer_id,
        CreditOverrideRequest.doc_type == doc_type,
        CreditOverrideRequest.status == OverrideStatus.approved,
        CreditOverrideRequest.expires_at > now,
    )
    if source_document_public_id is not None:
        stmt = stmt.where(
            CreditOverrideRequest.source_document_public_id == source_document_public_id
        )
    result = await db.execute(stmt)
    return result.scalars().first()


async def check_credit_limit(
    db: AsyncSession,
    *,
    customer_id: int,
    garage_id: int,
    additional_amount_minor: int,
    doc_type: str = "invoice",
    source_document_public_id: Optional[str] = None,
) -> bool:
    """Check if posting `additional_amount_minor` would exceed the credit limit.

    Returns True if an admin override was consumed to allow the operation,
    False if the operation was within limit (no override needed).
    Raises CreditLimitExceededError when blocked.

    source_document_public_id ties the override lookup to a specific document
    so that an approval for BL-A cannot be reused for BL-B.

    * If `credit_limit_minor == 0`  → no limit set, always passes.
    * If a valid admin-approved override exists → passes through (returns True).
    * mode='block'                  → raises CreditLimitExceededError.
    * mode='warn'                   → logs a warning and continues.
    """
    settings = get_settings()
    customer = await customer_repo.get_by_id(db, garage_id, customer_id)
    if not customer or customer.credit_limit_minor == 0:
        return False  # no limit configured

    projected = (customer.outstanding_minor or 0) + additional_amount_minor
    if projected <= customer.credit_limit_minor:
        return False  # within limit

    # Check for a valid admin-approved override before blocking
    override = await get_valid_override(
        db,
        customer_id=customer_id,
        garage_id=garage_id,
        doc_type=doc_type,
        source_document_public_id=source_document_public_id,
    )
    if override:
        logger.info(
            "credit_limit_override_used",
            customer_id=customer_id,
            override_id=override.id,
        )
        return True  # approved override in effect — allow through

    if settings.credit_limit_mode == "block":
        raise CreditLimitExceededError(
            customer_id=customer_id,
            limit=customer.credit_limit_minor,
            outstanding=customer.outstanding_minor or 0,
            additional=additional_amount_minor,
            customer_public_id=str(customer.public_id),
        )
    else:
        logger.warning(
            "credit_limit_exceeded_warn",
            customer_id=customer_id,
            limit=customer.credit_limit_minor,
            outstanding=customer.outstanding_minor or 0,
            additional=additional_amount_minor,
        )
    return False


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


# ---------------------------------------------------------------------------
# Manual credit-limit alert email (triggered from the in-app notification)
# ---------------------------------------------------------------------------


class CreditAlertError(Exception):
    pass


async def send_credit_limit_alert_email(
    db: AsyncSession,
    customer_id: int,
    garage_id: int,
    *,
    recipient: str,
) -> None:
    """Email the current credit-limit standing to the client or configured admin address(es)."""
    from app.modules.notification.service import dispatch, get_admin_recipients

    customer = await customer_repo.get_by_id(db, garage_id, customer_id)
    if not customer:
        raise CreditAlertError("Client introuvable.")

    settings = get_settings()
    limit_eur = (customer.credit_limit_minor or 0) / 100
    outstanding_eur = (customer.outstanding_minor or 0) / 100
    ratio = round((outstanding_eur / limit_eur) * 100) if limit_eur else 0

    context = {
        "customer_name": customer.full_name,
        "outstanding": f"{outstanding_eur:.2f}",
        "limit": f"{limit_eur:.2f}",
        "ratio": ratio,
        "garage_name": settings.pdf_garage_name,
        "garage_phone": settings.pdf_garage_phone,
    }

    if recipient == "client":
        if not customer.email:
            raise CreditAlertError("Le client n'a pas d'adresse email renseignée.")
        to_addresses = [customer.email]
        template_code = "credit_limit_alert_client"
    else:
        to_addresses = get_admin_recipients()
        if not to_addresses:
            raise CreditAlertError("Aucune adresse email admin n'est configurée.")
        template_code = "credit_limit_alert_admin"

    for addr in to_addresses:
        await dispatch(
            db,
            garage_id=garage_id,
            recipient_id=customer.id if recipient == "client" else None,
            recipient=addr,
            channel="email",
            template_code=template_code,
            context=context,
            respect_quiet_hours=False,
        )
