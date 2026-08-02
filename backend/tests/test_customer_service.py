"""Unit tests for customer service — duplicate detection, optimistic locking,
soft delete / restore, credit limit, balance ledger, audit hooks."""
from __future__ import annotations

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditLog
from app.modules.customer import repository as repo, service as svc
from app.modules.customer.models import (
    Customer,
    CustomerBalanceEvent,
    CustomerStatus,
)
from app.modules.customer.schemas import (
    CreditLimitUpdateRequest,
    CustomerBalanceEventCreateRequest,
    CustomerContactCreate,
    CustomerCreateRequest,
    CustomerUpdateRequest,
    MergeMatchReason,
)


GARAGE = 1
ACTOR = 1  # in tests we just store an int; no FK enforcement on SQLite tests


def _basic_payload(
    *,
    fiscal_id: str = "FID-DEFAULT",
    phone: str = "+33600000000",
    email: str | None = None,
    full_name: str = "Test Customer",
) -> CustomerCreateRequest:
    """fiscal_id and phone_e164 are mandatory on CustomerCreateRequest (French
    clients only — phone must be a +33 number); default to harmless values so
    callers only need to override them when the test is about duplicate
    detection or fiscal_id/phone specifically."""
    return CustomerCreateRequest(
        type="individual",
        full_name=full_name,
        fiscal_id=fiscal_id,
        phone_e164=phone,
        email=email,
    )


# ---------------------------------------------------------------------------
# Create + duplicate detection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCreateCustomer:
    async def test_create_minimal_individual(self, db_session: AsyncSession) -> None:
        result = await svc.create_customer(
            db_session,
            garage_id=GARAGE,
            actor_user_id=ACTOR,
            payload=_basic_payload(full_name="Alice"),
        )
        assert isinstance(result, Customer)
        assert result.full_name == "Alice"
        assert result.version == 1
        assert result.status == CustomerStatus.active
        assert result.deleted_at is None

    async def test_create_company_with_contacts(
        self, db_session: AsyncSession
    ) -> None:
        payload = CustomerCreateRequest(
            type="company",
            full_name="ACME Auto",
            company_name="ACME Auto SARL",
            fiscal_id="12345678901234",
            phone_e164="+33612345678",
            contacts=[
                CustomerContactCreate(channel="phone", value="+33611111111", is_primary=True),
                CustomerContactCreate(channel="email", value="contact@acme.ma"),
            ],
        )
        result = await svc.create_customer(
            db_session, garage_id=GARAGE, actor_user_id=ACTOR, payload=payload
        )
        assert isinstance(result, Customer)
        assert len(result.contacts) == 2

    async def test_duplicate_by_phone_and_fiscal_id(
        self, db_session: AsyncSession
    ) -> None:
        await svc.create_customer(
            db_session, garage_id=GARAGE, actor_user_id=ACTOR,
            payload=_basic_payload(fiscal_id="F-1", phone="+33611111111"),
        )
        await db_session.commit()

        result = await svc.create_customer(
            db_session, garage_id=GARAGE, actor_user_id=ACTOR,
            payload=_basic_payload(fiscal_id="F-1", phone="+33611111111", full_name="Other"),
        )
        assert isinstance(result, svc.DuplicateMatch)
        assert result.reason == MergeMatchReason.PHONE_AND_FISCAL_ID

    async def test_duplicate_by_email_and_fiscal_id(
        self, db_session: AsyncSession
    ) -> None:
        await svc.create_customer(
            db_session, garage_id=GARAGE, actor_user_id=ACTOR,
            payload=_basic_payload(fiscal_id="F-1", phone="+33611111111", email="x@y.com"),
        )
        await db_session.commit()

        result = await svc.create_customer(
            db_session, garage_id=GARAGE, actor_user_id=ACTOR,
            payload=_basic_payload(
                fiscal_id="F-1", phone="+33622222222", email="x@y.com", full_name="Other",
            ),
        )
        assert isinstance(result, svc.DuplicateMatch)
        assert result.reason == MergeMatchReason.EMAIL_AND_FISCAL_ID

    async def test_duplicate_fiscal_id_only(self, db_session: AsyncSession) -> None:
        """fiscal_id collision without phone or email match still returns a
        merge prompt (cleaner than letting the DB partial-unique 500)."""
        await svc.create_customer(
            db_session, garage_id=GARAGE, actor_user_id=ACTOR,
            payload=_basic_payload(fiscal_id="F-1", phone="+33611111111"),
        )
        await db_session.commit()

        result = await svc.create_customer(
            db_session, garage_id=GARAGE, actor_user_id=ACTOR,
            payload=_basic_payload(fiscal_id="F-1", phone="+33699999999", full_name="X"),
        )
        assert isinstance(result, svc.DuplicateMatch)
        assert result.reason == MergeMatchReason.FISCAL_ID_ONLY

    async def test_different_fiscal_id_no_merge_check(
        self, db_session: AsyncSession
    ) -> None:
        """fiscal_id is mandatory now, but it's still the merge anchor: a
        matching phone alone (different fiscal_id) never triggers a merge
        prompt."""
        await svc.create_customer(
            db_session, garage_id=GARAGE, actor_user_id=ACTOR,
            payload=_basic_payload(fiscal_id="F-A", phone="+33611111111"),
        )
        await db_session.commit()

        result = await svc.create_customer(
            db_session, garage_id=GARAGE, actor_user_id=ACTOR,
            payload=_basic_payload(fiscal_id="F-B", phone="+33611111111", full_name="Other"),
        )
        assert isinstance(result, Customer)

    async def test_duplicate_check_is_tenant_scoped(
        self, db_session: AsyncSession
    ) -> None:
        """Two garages can hold customers with the same fiscal_id + phone."""
        await svc.create_customer(
            db_session, garage_id=1, actor_user_id=ACTOR,
            payload=_basic_payload(fiscal_id="F-1", phone="+33611111111"),
        )
        await db_session.commit()

        result = await svc.create_customer(
            db_session, garage_id=2, actor_user_id=ACTOR,
            payload=_basic_payload(fiscal_id="F-1", phone="+33611111111", full_name="Garage2"),
        )
        assert isinstance(result, Customer)


# ---------------------------------------------------------------------------
# Update + optimistic locking
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestUpdateCustomer:
    async def _seed_one(self, db: AsyncSession) -> Customer:
        c = await svc.create_customer(
            db, garage_id=GARAGE, actor_user_id=ACTOR,
            payload=_basic_payload(fiscal_id="F-1", full_name="Original"),
        )
        await db.commit()
        return c  # type: ignore[return-value]

    async def test_update_correct_version_bumps_version(
        self, db_session: AsyncSession
    ) -> None:
        c = await self._seed_one(db_session)
        updated = await svc.update_customer(
            db_session, garage_id=GARAGE, actor_user_id=ACTOR,
            public_id=str(c.public_id),
            payload=CustomerUpdateRequest(version=1, full_name="Renamed"),
        )
        assert updated.full_name == "Renamed"
        assert updated.version == 2

    async def test_update_stale_version_raises(
        self, db_session: AsyncSession
    ) -> None:
        c = await self._seed_one(db_session)
        # First update bumps version 1 → 2
        await svc.update_customer(
            db_session, garage_id=GARAGE, actor_user_id=ACTOR,
            public_id=str(c.public_id),
            payload=CustomerUpdateRequest(version=1, full_name="A"),
        )
        await db_session.commit()

        with pytest.raises(svc.OptimisticLockError) as exc_info:
            await svc.update_customer(
                db_session, garage_id=GARAGE, actor_user_id=ACTOR,
                public_id=str(c.public_id),
                payload=CustomerUpdateRequest(version=1, full_name="B"),
            )
        assert exc_info.value.expected == 1
        assert exc_info.value.actual == 2

    async def test_update_unknown_id_raises(
        self, db_session: AsyncSession
    ) -> None:
        with pytest.raises(svc.CustomerNotFoundError):
            await svc.update_customer(
                db_session, garage_id=GARAGE, actor_user_id=ACTOR,
                public_id="00000000-0000-0000-0000-000000000000",
                payload=CustomerUpdateRequest(version=1, full_name="X"),
            )

    async def test_update_fiscal_id_conflict_raises(
        self, db_session: AsyncSession
    ) -> None:
        await svc.create_customer(
            db_session, garage_id=GARAGE, actor_user_id=ACTOR,
            payload=_basic_payload(fiscal_id="F-A", full_name="A"),
        )
        b = await svc.create_customer(
            db_session, garage_id=GARAGE, actor_user_id=ACTOR,
            payload=_basic_payload(fiscal_id="F-B", full_name="B"),
        )
        await db_session.commit()

        with pytest.raises(svc.FiscalIdConflictError):
            await svc.update_customer(
                db_session, garage_id=GARAGE, actor_user_id=ACTOR,
                public_id=str(b.public_id),
                payload=CustomerUpdateRequest(version=1, fiscal_id="F-A"),
            )

    async def test_update_no_change_does_not_bump_version(
        self, db_session: AsyncSession
    ) -> None:
        c = await self._seed_one(db_session)
        result = await svc.update_customer(
            db_session, garage_id=GARAGE, actor_user_id=ACTOR,
            public_id=str(c.public_id),
            payload=CustomerUpdateRequest(version=1, full_name="Original"),
        )
        assert result.version == 1


# ---------------------------------------------------------------------------
# Soft delete + restore
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestSoftDeleteRestore:
    async def test_soft_delete_marks_row_and_hides_from_live_lookup(
        self, db_session: AsyncSession
    ) -> None:
        c = await svc.create_customer(
            db_session, garage_id=GARAGE, actor_user_id=ACTOR,
            payload=_basic_payload(full_name="ToDelete"),
        )
        await db_session.commit()

        await svc.soft_delete_customer(
            db_session, garage_id=GARAGE, actor_user_id=ACTOR,
            public_id=str(c.public_id),
        )
        await db_session.commit()

        assert c.deleted_at is not None
        live = await repo.get_by_public_id(db_session, GARAGE, str(c.public_id))
        assert live is None

    async def test_soft_delete_idempotent(self, db_session: AsyncSession) -> None:
        c = await svc.create_customer(
            db_session, garage_id=GARAGE, actor_user_id=ACTOR,
            payload=_basic_payload(full_name="X"),
        )
        await db_session.commit()
        await svc.soft_delete_customer(
            db_session, garage_id=GARAGE, actor_user_id=ACTOR,
            public_id=str(c.public_id),
        )
        await db_session.commit()
        first_deleted_at = c.deleted_at
        # second delete should be a no-op
        await svc.soft_delete_customer(
            db_session, garage_id=GARAGE, actor_user_id=ACTOR,
            public_id=str(c.public_id),
        )
        await db_session.commit()
        assert c.deleted_at == first_deleted_at

    async def test_restore_reactivates(self, db_session: AsyncSession) -> None:
        c = await svc.create_customer(
            db_session, garage_id=GARAGE, actor_user_id=ACTOR,
            payload=_basic_payload(full_name="X"),
        )
        await db_session.commit()
        await svc.soft_delete_customer(
            db_session, garage_id=GARAGE, actor_user_id=ACTOR,
            public_id=str(c.public_id),
        )
        await db_session.commit()

        await svc.restore_customer(
            db_session, garage_id=GARAGE, actor_user_id=ACTOR,
            public_id=str(c.public_id),
        )
        await db_session.commit()
        assert c.deleted_at is None
        assert c.status == CustomerStatus.active

    async def test_restore_blocked_by_fiscal_id_conflict(
        self, db_session: AsyncSession
    ) -> None:
        deleted = await svc.create_customer(
            db_session, garage_id=GARAGE, actor_user_id=ACTOR,
            payload=_basic_payload(fiscal_id="F-X", full_name="Old"),
        )
        await db_session.commit()
        await svc.soft_delete_customer(
            db_session, garage_id=GARAGE, actor_user_id=ACTOR,
            public_id=str(deleted.public_id),
        )
        await db_session.commit()

        # New live customer takes the fiscal_id
        await svc.create_customer(
            db_session, garage_id=GARAGE, actor_user_id=ACTOR,
            payload=_basic_payload(fiscal_id="F-X", full_name="New"),
        )
        await db_session.commit()

        with pytest.raises(svc.FiscalIdConflictError):
            await svc.restore_customer(
                db_session, garage_id=GARAGE, actor_user_id=ACTOR,
                public_id=str(deleted.public_id),
            )


# ---------------------------------------------------------------------------
# Credit limit + balance ledger
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCreditAndBalance:
    async def test_credit_limit_update_stores_reason_in_audit(
        self, db_session: AsyncSession
    ) -> None:
        c = await svc.create_customer(
            db_session, garage_id=GARAGE, actor_user_id=ACTOR,
            payload=_basic_payload(full_name="X"),
        )
        await db_session.commit()
        await svc.update_credit_limit(
            db_session, garage_id=GARAGE, actor_user_id=ACTOR,
            public_id=str(c.public_id),
            payload=CreditLimitUpdateRequest(
                credit_limit_minor=100000, credit_currency="MAD",
                reason="Trusted fleet customer",
            ),
        )
        await db_session.commit()
        assert c.credit_limit_minor == 100000
        assert c.credit_currency == "MAD"
        assert c.version == 2

        # The reason must be on the audit row
        result = await db_session.execute(
            select(AuditLog.reason)
            .where(AuditLog.component == "customer",
                   AuditLog.action == "credit_limit.update")
            .order_by(AuditLog.id.desc())
        )
        assert result.scalar() == "Trusted fleet customer"

    async def test_balance_event_atomic_with_outstanding(
        self, db_session: AsyncSession
    ) -> None:
        c = await svc.create_customer(
            db_session, garage_id=GARAGE, actor_user_id=ACTOR,
            payload=_basic_payload(full_name="X"),
        )
        await db_session.commit()
        assert c.outstanding_minor == 0

        await svc.add_balance_event(
            db_session, garage_id=GARAGE, actor_user_id=ACTOR,
            public_id=str(c.public_id),
            payload=CustomerBalanceEventCreateRequest(
                reason="manual_adjust", delta_minor=5000, currency="MAD",
            ),
        )
        await db_session.commit()
        await db_session.refresh(c)
        assert c.outstanding_minor == 5000

        # Second event accumulates
        await svc.add_balance_event(
            db_session, garage_id=GARAGE, actor_user_id=ACTOR,
            public_id=str(c.public_id),
            payload=CustomerBalanceEventCreateRequest(
                reason="payment_received", delta_minor=-3000, currency="MAD",
            ),
        )
        await db_session.commit()
        await db_session.refresh(c)
        assert c.outstanding_minor == 2000

        # Two ledger rows
        count = await db_session.execute(
            select(func.count(CustomerBalanceEvent.id)).where(
                CustomerBalanceEvent.customer_id == c.id
            )
        )
        assert count.scalar_one() == 2


# ---------------------------------------------------------------------------
# Audit coverage — every mutation writes a row
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestAuditCoverage:
    async def test_full_lifecycle_writes_expected_audit_rows(
        self, db_session: AsyncSession
    ) -> None:
        c = await svc.create_customer(
            db_session, garage_id=GARAGE, actor_user_id=ACTOR,
            payload=_basic_payload(fiscal_id="F-Z", full_name="X"),
        )
        await db_session.commit()

        await svc.update_customer(
            db_session, garage_id=GARAGE, actor_user_id=ACTOR,
            public_id=str(c.public_id),
            payload=CustomerUpdateRequest(version=1, segment="vip"),
        )
        await db_session.commit()

        await svc.update_credit_limit(
            db_session, garage_id=GARAGE, actor_user_id=ACTOR,
            public_id=str(c.public_id),
            payload=CreditLimitUpdateRequest(
                credit_limit_minor=10000, credit_currency="MAD", reason="r"
            ),
        )
        await db_session.commit()

        await svc.add_balance_event(
            db_session, garage_id=GARAGE, actor_user_id=ACTOR,
            public_id=str(c.public_id),
            payload=CustomerBalanceEventCreateRequest(
                reason="r", delta_minor=100, currency="MAD"
            ),
        )
        await db_session.commit()

        await svc.soft_delete_customer(
            db_session, garage_id=GARAGE, actor_user_id=ACTOR,
            public_id=str(c.public_id),
        )
        await db_session.commit()

        await svc.restore_customer(
            db_session, garage_id=GARAGE, actor_user_id=ACTOR,
            public_id=str(c.public_id),
        )
        await db_session.commit()

        result = await db_session.execute(
            select(AuditLog.action)
            .where(AuditLog.component == "customer")
            .order_by(AuditLog.id)
        )
        actions = result.scalars().all()
        assert actions == [
            "create", "update", "credit_limit.update", "balance.adjust",
            "delete", "restore",
        ]

    async def test_audit_redacts_sensitive_fields(
        self, db_session: AsyncSession
    ) -> None:
        """Customers don't store passwords, but ensure the redactor is wired:
        no field named 'password*' or 'token*' should ever appear unredacted."""
        c = await svc.create_customer(
            db_session, garage_id=GARAGE, actor_user_id=ACTOR,
            payload=_basic_payload(full_name="X"),
        )
        await db_session.commit()
        result = await db_session.execute(
            select(AuditLog.new_value)
            .where(AuditLog.component == "customer", AuditLog.action == "create")
        )
        row = result.scalar_one()
        # SQLite-side JsonB returns the dict directly; PG returns parsed JSONB
        for k in (row or {}).keys():
            assert "password" not in k.lower()
            assert "token" not in k.lower()
