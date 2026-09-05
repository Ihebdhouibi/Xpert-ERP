"""
KPI computation service.

All queries are written as raw SQL via text() for performance — these are
aggregation queries across multiple tables and SQLAlchemy ORM chains would
be significantly slower to write and execute.

Each KPI returns (value: Decimal | None, meta: Any | None).
Monetary values are stored in minor units (cents) as Decimal.
Percentages are stored as Decimal(0-100).
Counts are stored as integers cast to Decimal.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.redis import get_redis

logger = get_logger("kpi.service")

# KPI catalog — codes used as kpi_code in snapshots
KPI_CODES = [
    "revenue_mtd",
    "revenue_ytd",
    "margin_avg_pct",
    "workshop_occupancy_pct",
    "avg_repair_duration_h",
    "avg_immobilization_h",
    "unpaid_invoices_count",
    "outstanding_amount_minor",
    "open_repair_orders_count",
    "low_stock_alerts_count",
    "top_customers",
    "top_suppliers",
    "comeback_rate_pct",
    "quotation_conversion_rate_pct",
]

_CACHE_KEY_PREFIX = "kpi:live:"


# ---------------------------------------------------------------------------
# Individual KPI computations
# ---------------------------------------------------------------------------


async def revenue_for_period(
    db: AsyncSession, garage_id: int, from_date: date, to_date: date
) -> Decimal:
    """
    Net "chiffre d'affaires" for [from_date, to_date] (inclusive), cash basis:

      + total_minor of invoices that are fully PAID, dated by the moment they
        actually became paid — i.e. the latest of any payment.paid_at or
        advance_payment.applied_at that settled them — NOT the invoice's
        issue date. Revenue is recognised when the cash is actually
        collected (or already-held advance credit consumed), not when
        billed. An invoice fully settled by advance credit alone has ZERO
        rows in `payment` — a plain JOIN to payment would silently drop it
        (found via a real ~580€ discrepancy while auditing the ledger), so
        settlement is reconstructed from BOTH tables.
      - total_minor of credit notes (avoirs) ISSUED in the period, dated by
        their own issued_at. An avoir reduces the revenue of the period it
        was granted in, regardless of which period the original invoice's
        revenue was booked in.

    This is the one true definition of CA used across the app (live KPIs,
    the KPI dashboard's trend chart, and the Dashboard's period-picker card)
    — see revenue_mtd/revenue_ytd below and compute_analytics's revenue_trend.
    """
    row = await db.execute(
        text(
            """
            WITH settlement_events AS (
                SELECT p.invoice_id AS inv_id, p.paid_at AS event_at
                FROM payment p
                UNION ALL
                SELECT ap.applied_to_invoice_id AS inv_id, ap.applied_at AS event_at
                FROM advance_payment ap
                WHERE ap.applied_to_invoice_id IS NOT NULL
            ),
            settled AS (
                SELECT i.id, i.total_minor, MAX(se.event_at) AS settled_at
                FROM invoice i
                JOIN settlement_events se ON se.inv_id = i.id
                WHERE i.garage_id = :g
                  AND i.status = 'paid'
                  AND i.deleted_at IS NULL
                GROUP BY i.id, i.total_minor
            ),
            paid_revenue AS (
                SELECT COALESCE(SUM(total_minor), 0) AS amt
                FROM settled
                WHERE (settled_at AT TIME ZONE 'UTC')::date BETWEEN :from_d AND :to_d
            ),
            avoirs AS (
                SELECT COALESCE(SUM(total_minor), 0) AS amt
                FROM credit_note
                WHERE garage_id = :g
                  AND status = 'issued'
                  AND (issued_at AT TIME ZONE 'UTC')::date BETWEEN :from_d AND :to_d
            )
            SELECT (SELECT amt FROM paid_revenue) - (SELECT amt FROM avoirs)
            """
        ),
        {"g": garage_id, "from_d": from_date, "to_d": to_date},
    )
    return Decimal(row.scalar() or 0)


async def _revenue_mtd(db: AsyncSession, garage_id: int) -> tuple[Optional[Decimal], None]:
    today = datetime.now(tz=timezone.utc).date()
    value = await revenue_for_period(db, garage_id, today.replace(day=1), today)
    return value, None


async def _revenue_ytd(db: AsyncSession, garage_id: int) -> tuple[Optional[Decimal], None]:
    today = datetime.now(tz=timezone.utc).date()
    value = await revenue_for_period(db, garage_id, today.replace(month=1, day=1), today)
    return value, None


async def _margin_avg_pct(db: AsyncSession, garage_id: int) -> tuple[Optional[Decimal], None]:
    """
    Average margin % = (revenue - parts_cost) / revenue * 100
    Computed over invoices issued this month linked to repair orders.
    parts_cost = sum of ro_part_line.amount_minor on those ROs.
    """
    row = await db.execute(
        text(
            """
            WITH invoice_ro AS (
                SELECT i.id AS inv_id,
                       i.repair_order_id AS ro_id,
                       i.total_minor
                FROM invoice i
                WHERE i.garage_id = :g
                  AND i.status IN ('issued', 'partial', 'paid')
                  AND i.repair_order_id IS NOT NULL
                  AND i.issued_at >= date_trunc('month', now() AT TIME ZONE 'UTC')
                  AND i.deleted_at IS NULL
            ),
            parts_cost AS (
                SELECT pl.ro_id, COALESCE(SUM(pl.amount_minor), 0) AS cost
                FROM ro_part_line pl
                INNER JOIN invoice_ro ir ON ir.ro_id = pl.ro_id
                GROUP BY pl.ro_id
            )
            SELECT
              CASE
                WHEN SUM(ir.total_minor) = 0 THEN NULL
                ELSE ROUND(
                  (SUM(ir.total_minor) - COALESCE(SUM(pc.cost), 0))::NUMERIC
                  / SUM(ir.total_minor) * 100, 2
                )
              END
            FROM invoice_ro ir
            LEFT JOIN parts_cost pc ON pc.ro_id = ir.ro_id
            """
        ),
        {"g": garage_id},
    )
    val = row.scalar()
    return (Decimal(val) if val is not None else None), None


async def _workshop_occupancy_pct(
    db: AsyncSession, garage_id: int, capacity: int
) -> tuple[Optional[Decimal], None]:
    """Open ROs (not delivered, not soft-deleted) as % of workshop capacity."""
    row = await db.execute(
        text(
            """
            SELECT COUNT(*)
            FROM repair_order
            WHERE garage_id = :g
              AND status NOT IN ('delivered')
              AND deleted_at IS NULL
            """
        ),
        {"g": garage_id},
    )
    count = row.scalar() or 0
    if capacity <= 0:
        return None, None
    pct = min(Decimal(count) / Decimal(capacity) * 100, Decimal(100))
    return pct.quantize(Decimal("0.01")), None


async def _avg_repair_duration_h(db: AsyncSession, garage_id: int) -> tuple[Optional[Decimal], None]:
    """Average hours from RO creation to delivered status event, last 90 days."""
    row = await db.execute(
        text(
            """
            SELECT ROUND(AVG(
                EXTRACT(EPOCH FROM (e.occurred_at - ro.created_at)) / 3600.0
            )::NUMERIC, 2)
            FROM repair_order ro
            JOIN ro_status_event e
                ON e.ro_id = ro.id
               AND e.new_status = 'delivered'
            WHERE ro.garage_id = :g
              AND ro.deleted_at IS NULL
              AND e.occurred_at >= now() AT TIME ZONE 'UTC' - INTERVAL '90 days'
            """
        ),
        {"g": garage_id},
    )
    val = row.scalar()
    return (Decimal(val) if val is not None else None), None


async def _avg_immobilization_h(db: AsyncSession, garage_id: int) -> tuple[Optional[Decimal], None]:
    """
    Average vehicle immobilization time (hours) = time from RO creation until
    delivery (or now if still open), for ROs active in the last 90 days.
    """
    row = await db.execute(
        text(
            """
            SELECT ROUND(AVG(
                EXTRACT(EPOCH FROM (
                    COALESCE(e.occurred_at, now() AT TIME ZONE 'UTC') - ro.created_at
                )) / 3600.0
            )::NUMERIC, 2)
            FROM repair_order ro
            LEFT JOIN LATERAL (
                SELECT occurred_at
                FROM ro_status_event
                WHERE ro_id = ro.id AND new_status = 'delivered'
                ORDER BY occurred_at DESC
                LIMIT 1
            ) e ON TRUE
            WHERE ro.garage_id = :g
              AND ro.deleted_at IS NULL
              AND ro.created_at >= now() AT TIME ZONE 'UTC' - INTERVAL '90 days'
            """
        ),
        {"g": garage_id},
    )
    val = row.scalar()
    return (Decimal(val) if val is not None else None), None


async def _unpaid_invoices_count(db: AsyncSession, garage_id: int) -> tuple[Optional[Decimal], None]:
    """Count of invoices with outstanding amount > 0."""
    row = await db.execute(
        text(
            """
            SELECT COUNT(*)
            FROM invoice
            WHERE garage_id = :g
              AND status IN ('issued', 'partial')
              AND outstanding_minor > 0
              AND deleted_at IS NULL
            """
        ),
        {"g": garage_id},
    )
    return Decimal(row.scalar() or 0), None


async def _outstanding_amount_minor(db: AsyncSession, garage_id: int) -> tuple[Optional[Decimal], None]:
    """Total customer outstanding balance, right now.

    Reads customer.outstanding_minor — the denormalised snapshot that
    post_balance_event() keeps in lockstep with the customer_balance_event
    ledger on every write. Previously this summed invoice.outstanding_minor
    directly, which silently ignored avoirs issued against still-open
    invoices (issue_credit_note only ever posts to the ledger, by design it
    never touches the invoice row) — so it overstated what customers
    actually owe. The ledger-backed snapshot is the same number credit-limit
    enforcement already trusts (check_credit_limit in credit_service.py);
    this makes it one consistent source of truth instead of two disagreeing
    ones. See outstanding_as_of() below for historical ("as of a past date")
    lookups, which this snapshot can't answer since it has no memory.
    """
    row = await db.execute(
        text(
            """
            SELECT COALESCE(SUM(outstanding_minor), 0)
            FROM customer
            WHERE garage_id = :g
            """
        ),
        {"g": garage_id},
    )
    return Decimal(row.scalar() or 0), None


async def outstanding_as_of(db: AsyncSession, garage_id: int, as_of_date: date) -> Decimal:
    """Total customer outstanding balance as of the end of as_of_date (inclusive).

    Reconstructed directly from the append-only customer_balance_event
    ledger — summing every event up to and including that date — rather
    than from any batch-computed snapshot (the daily kpi_snapshot table
    exists but has real gaps in practice, e.g. after a process restart
    misses its scheduled run). This is always accurate for any date,
    including today, at the cost of a full ledger scan per call — fine for
    an on-demand, user-triggered lookup; _outstanding_amount_minor above
    stays the fast path for the constantly-polled /kpi/live.
    """
    row = await db.execute(
        text(
            """
            SELECT COALESCE(SUM(e.delta_minor), 0)
            FROM customer_balance_event e
            JOIN customer c ON c.id = e.customer_id
            WHERE c.garage_id = :g
              AND (e.occurred_at AT TIME ZONE 'UTC')::date <= :as_of
            """
        ),
        {"g": garage_id, "as_of": as_of_date},
    )
    return Decimal(row.scalar() or 0)


async def _top_customers(
    db: AsyncSession, garage_id: int
) -> tuple[Optional[Decimal], Optional[list[dict]]]:
    """Top 10 customers by total invoiced revenue (issued/partial/paid)."""
    result = await db.execute(
        text(
            """
            SELECT c.id, c.public_id::text, c.full_name,
                   COALESCE(SUM(i.total_minor), 0) AS revenue_minor
            FROM customer c
            JOIN invoice i ON i.customer_id = c.id
            WHERE i.garage_id = :g
              AND i.status IN ('issued', 'partial', 'paid')
              AND i.deleted_at IS NULL
              AND c.deleted_at IS NULL
            GROUP BY c.id, c.public_id, c.full_name
            ORDER BY revenue_minor DESC
            LIMIT 10
            """
        ),
        {"g": garage_id},
    )
    rows = result.fetchall()
    if not rows:
        return Decimal(0), []
    meta = [
        {
            "rank": idx + 1,
            "customer_id": str(r.public_id),
            "name": r.full_name,
            "revenue_minor": int(r.revenue_minor),
        }
        for idx, r in enumerate(rows)
    ]
    total_revenue = sum(r.revenue_minor for r in rows)
    return Decimal(total_revenue), meta


async def _top_suppliers(
    db: AsyncSession, garage_id: int
) -> tuple[Optional[Decimal], Optional[list[dict]]]:
    """Top 10 suppliers by total purchase order spend (total_ht)."""
    result = await db.execute(
        text(
            """
            SELECT s.id, s.public_id::text, s.name,
                   COALESCE(SUM(po.total_ht), 0) AS spend_minor
            FROM supplier s
            JOIN purchase_order po ON po.supplier_id = s.id
            WHERE po.garage_id = :g
              AND po.status NOT IN ('cancelled')
              AND po.deleted_at IS NULL
              AND s.deleted_at IS NULL
            GROUP BY s.id, s.public_id, s.name
            ORDER BY spend_minor DESC
            LIMIT 10
            """
        ),
        {"g": garage_id},
    )
    rows = result.fetchall()
    if not rows:
        return Decimal(0), []
    meta = [
        {
            "rank": idx + 1,
            "supplier_id": str(r.public_id),
            "name": r.name,
            "spend_minor": int(r.spend_minor),
        }
        for idx, r in enumerate(rows)
    ]
    total_spend = sum(r.spend_minor for r in rows)
    return Decimal(total_spend), meta


async def _comeback_rate_pct(db: AsyncSession, garage_id: int) -> tuple[Optional[Decimal], None]:
    """
    Comeback = RO on a vehicle that had another delivered RO completed within 30 days before it.
    Rate = comebacks / all vehicle-linked ROs created in last 90 days * 100.
    """
    row = await db.execute(
        text(
            """
            SELECT
              CASE WHEN COUNT(*) = 0 THEN NULL
              ELSE ROUND(
                COUNT(CASE WHEN prev.id IS NOT NULL THEN 1 END)::NUMERIC
                / COUNT(*) * 100, 2
              )
              END
            FROM repair_order ro
            LEFT JOIN LATERAL (
                SELECT prev_ro.id
                FROM repair_order prev_ro
                JOIN ro_status_event se
                    ON se.ro_id = prev_ro.id
                   AND se.new_status = 'delivered'
                WHERE prev_ro.vehicle_id = ro.vehicle_id
                  AND prev_ro.garage_id = ro.garage_id
                  AND prev_ro.id != ro.id
                  AND se.occurred_at >= ro.created_at - INTERVAL '30 days'
                  AND se.occurred_at < ro.created_at
                  AND prev_ro.deleted_at IS NULL
                LIMIT 1
            ) prev ON TRUE
            WHERE ro.garage_id = :g
              AND ro.vehicle_id IS NOT NULL
              AND ro.deleted_at IS NULL
              AND ro.created_at >= now() AT TIME ZONE 'UTC' - INTERVAL '90 days'
            """
        ),
        {"g": garage_id},
    )
    val = row.scalar()
    return (Decimal(val) if val is not None else None), None


async def _open_repair_orders_count(db: AsyncSession, garage_id: int) -> tuple[Optional[Decimal], None]:
    """Count of repair orders not yet delivered."""
    row = await db.execute(
        text(
            """
            SELECT COUNT(*)
            FROM repair_order
            WHERE garage_id = :g
              AND status NOT IN ('delivered')
              AND deleted_at IS NULL
            """
        ),
        {"g": garage_id},
    )
    return Decimal(row.scalar() or 0), None


async def _low_stock_alerts_count(db: AsyncSession, garage_id: int) -> tuple[Optional[Decimal], None]:
    """Count of open (unacknowledged) low-stock alerts."""
    row = await db.execute(
        text(
            """
            SELECT COUNT(*)
            FROM low_stock_alert
            WHERE garage_id = :g
              AND status = 'open'
            """
        ),
        {"g": garage_id},
    )
    return Decimal(row.scalar() or 0), None


async def _quotation_conversion_rate_pct(
    db: AsyncSession, garage_id: int
) -> tuple[Optional[Decimal], None]:
    """Converted quotations / terminal quotations (sent+approved+rejected+expired+converted) * 100."""
    row = await db.execute(
        text(
            """
            SELECT
              CASE WHEN COUNT(*) = 0 THEN NULL
              ELSE ROUND(
                COUNT(CASE WHEN status = 'converted' THEN 1 END)::NUMERIC
                / COUNT(*) * 100, 2
              )
              END
            FROM quotation
            WHERE garage_id = :g
              AND status IN ('sent', 'approved', 'rejected', 'expired', 'converted')
              AND deleted_at IS NULL
            """
        ),
        {"g": garage_id},
    )
    val = row.scalar()
    return (Decimal(val) if val is not None else None), None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def compute_all_kpis(
    db: AsyncSession, garage_id: int
) -> dict[str, tuple[Optional[Decimal], Optional[Any]]]:
    """
    Compute all KPIs for garage_id. Returns a dict of
    kpi_code -> (value, meta).

    All queries run concurrently via asyncio.gather would require separate
    connections; instead we run them sequentially but each is a single SQL
    round-trip, so total time stays well under 5s at expected data volumes.
    """
    logger.info("compute_all_kpis_start", garage_id=garage_id)
    settings = get_settings()
    capacity = getattr(settings, "cfg_kpi_workshop_capacity", 10)

    results: dict[str, tuple[Optional[Decimal], Optional[Any]]] = {}

    results["revenue_mtd"] = await _revenue_mtd(db, garage_id)
    results["revenue_ytd"] = await _revenue_ytd(db, garage_id)
    results["margin_avg_pct"] = await _margin_avg_pct(db, garage_id)
    results["workshop_occupancy_pct"] = await _workshop_occupancy_pct(db, garage_id, capacity)
    results["avg_repair_duration_h"] = await _avg_repair_duration_h(db, garage_id)
    results["avg_immobilization_h"] = await _avg_immobilization_h(db, garage_id)
    results["unpaid_invoices_count"] = await _unpaid_invoices_count(db, garage_id)
    results["outstanding_amount_minor"] = await _outstanding_amount_minor(db, garage_id)
    results["open_repair_orders_count"] = await _open_repair_orders_count(db, garage_id)
    results["low_stock_alerts_count"] = await _low_stock_alerts_count(db, garage_id)
    results["top_customers"] = await _top_customers(db, garage_id)
    results["top_suppliers"] = await _top_suppliers(db, garage_id)
    results["comeback_rate_pct"] = await _comeback_rate_pct(db, garage_id)
    results["quotation_conversion_rate_pct"] = await _quotation_conversion_rate_pct(db, garage_id)

    return results


async def get_live_kpis(db: AsyncSession, garage_id: int) -> dict[str, Any]:
    """
    Return live KPIs, served from Redis cache when still fresh.
    On cache miss, recomputes from DB and repopulates the cache.
    """
    logger.info("get_live_kpis_start", garage_id=garage_id)
    settings = get_settings()
    ttl = settings.cfg_kpi_refresh_interval_seconds
    cache_key = f"{_CACHE_KEY_PREFIX}{garage_id}"

    try:
        redis = get_redis()
        cached = await redis.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception:
        logger.warning("kpi_cache_read_failed", exc_info=True)

    kpi_data = await compute_all_kpis(db, garage_id)

    payload: dict[str, Any] = {
        "garage_id": garage_id,
        "computed_at": datetime.now(tz=timezone.utc).isoformat(),
        "refresh_interval_seconds": ttl,
        "kpis": {},
    }
    for code, (value, meta) in kpi_data.items():
        payload["kpis"][code] = {
            "value": float(value) if value is not None else None,
            "meta": meta,
        }

    try:
        redis = get_redis()
        await redis.setex(cache_key, ttl, json.dumps(payload))
    except Exception:
        logger.warning("kpi_cache_write_failed", exc_info=True)

    return payload


async def compute_analytics(
    db: AsyncSession,
    garage_id: int,
    from_date: date,
    to_date: date,
) -> dict[str, Any]:
    """
    Compute period-scoped analytics for charts.
    Returns daily revenue trend, daily repair count trend, and per-mechanic productivity.
    """
    # Net daily revenue = paid invoices settled that day − avoirs issued that day
    # (same cash-basis, avoir-deducted definition as revenue_for_period — see
    # its docstring for why settlement is reconstructed from BOTH payment and
    # advance_payment, not payment alone). A day backbone via generate_series
    # is required to net both sides correctly even when only one of the two
    # has activity on a given day.
    revenue_result = await db.execute(
        text(
            """
            WITH days AS (
                SELECT generate_series(:from_d::date, :to_d::date, interval '1 day')::date AS day
            ),
            settlement_events AS (
                SELECT p.invoice_id AS inv_id, p.paid_at AS event_at
                FROM payment p
                UNION ALL
                SELECT ap.applied_to_invoice_id AS inv_id, ap.applied_at AS event_at
                FROM advance_payment ap
                WHERE ap.applied_to_invoice_id IS NOT NULL
            ),
            settled AS (
                SELECT i.id, i.total_minor, MAX(se.event_at) AS settled_at
                FROM invoice i
                JOIN settlement_events se ON se.inv_id = i.id
                WHERE i.garage_id = :g
                  AND i.status = 'paid'
                  AND i.deleted_at IS NULL
                GROUP BY i.id, i.total_minor
            ),
            paid_by_day AS (
                SELECT (settled_at AT TIME ZONE 'UTC')::date AS day,
                       SUM(total_minor) AS amt
                FROM settled
                WHERE (settled_at AT TIME ZONE 'UTC')::date BETWEEN :from_d AND :to_d
                GROUP BY day
            ),
            avoirs_by_day AS (
                SELECT (issued_at AT TIME ZONE 'UTC')::date AS day,
                       SUM(total_minor) AS amt
                FROM credit_note
                WHERE garage_id = :g
                  AND status = 'issued'
                  AND (issued_at AT TIME ZONE 'UTC')::date BETWEEN :from_d AND :to_d
                GROUP BY day
            )
            SELECT d.day AS day,
                   (COALESCE(pb.amt, 0) - COALESCE(ab.amt, 0))::bigint AS amount_minor
            FROM days d
            LEFT JOIN paid_by_day pb ON pb.day = d.day
            LEFT JOIN avoirs_by_day ab ON ab.day = d.day
            ORDER BY d.day
            """
        ),
        {"g": garage_id, "from_d": from_date, "to_d": to_date},
    )
    revenue_trend = [
        {"date": str(r.day), "value": int(r.amount_minor)}
        for r in revenue_result.fetchall()
    ]

    repair_result = await db.execute(
        text(
            """
            SELECT (e.occurred_at AT TIME ZONE 'UTC')::date AS day,
                   COUNT(DISTINCT e.ro_id)::bigint AS count
            FROM ro_status_event e
            JOIN repair_order ro ON ro.id = e.ro_id
            WHERE ro.garage_id = :g
              AND e.new_status = 'delivered'
              AND (e.occurred_at AT TIME ZONE 'UTC')::date BETWEEN :from_d AND :to_d
              AND ro.deleted_at IS NULL
            GROUP BY day
            ORDER BY day
            """
        ),
        {"g": garage_id, "from_d": from_date, "to_d": to_date},
    )
    repair_count_trend = [
        {"date": str(r.day), "value": int(r.count)}
        for r in repair_result.fetchall()
    ]

    mechanic_result = await db.execute(
        text(
            """
            SELECT u.full_name,
                   COUNT(DISTINCT e.ro_id)::bigint AS completed_count,
                   ROUND(AVG(
                       EXTRACT(EPOCH FROM (e.occurred_at - ro.created_at)) / 3600.0
                   )::NUMERIC, 2) AS avg_duration_h
            FROM ro_status_event e
            JOIN repair_order ro ON ro.id = e.ro_id
            JOIN app_user u ON u.id = ro.assigned_user_id
            WHERE ro.garage_id = :g
              AND e.new_status = 'delivered'
              AND (e.occurred_at AT TIME ZONE 'UTC')::date BETWEEN :from_d AND :to_d
              AND ro.deleted_at IS NULL
              AND u.deleted_at IS NULL
            GROUP BY u.id, u.full_name
            ORDER BY completed_count DESC
            """
        ),
        {"g": garage_id, "from_d": from_date, "to_d": to_date},
    )
    mechanic_productivity = [
        {
            "name": r.full_name,
            "completed_count": int(r.completed_count),
            "avg_duration_h": float(r.avg_duration_h) if r.avg_duration_h is not None else None,
        }
        for r in mechanic_result.fetchall()
    ]

    # Outstanding balance, day by day — a running total (stock), not a daily
    # net (flow) like revenue_trend above. "base" is everything that happened
    # strictly before from_date; the window function then adds each day's own
    # ledger activity cumulatively on top, so day N = true balance as of N,
    # not just activity within the visible range. Reconstructed live from the
    # ledger rather than the daily kpi_snapshot table — see outstanding_as_of.
    outstanding_result = await db.execute(
        text(
            """
            WITH days AS (
                SELECT generate_series(:from_d::date, :to_d::date, interval '1 day')::date AS day
            ),
            base AS (
                SELECT COALESCE(SUM(e.delta_minor), 0) AS amt
                FROM customer_balance_event e
                JOIN customer c ON c.id = e.customer_id
                WHERE c.garage_id = :g
                  AND (e.occurred_at AT TIME ZONE 'UTC')::date < :from_d
            ),
            daily_delta AS (
                SELECT (e.occurred_at AT TIME ZONE 'UTC')::date AS day,
                       SUM(e.delta_minor) AS delta
                FROM customer_balance_event e
                JOIN customer c ON c.id = e.customer_id
                WHERE c.garage_id = :g
                  AND (e.occurred_at AT TIME ZONE 'UTC')::date BETWEEN :from_d AND :to_d
                GROUP BY day
            )
            SELECT d.day AS day,
                   ((SELECT amt FROM base)
                     + SUM(COALESCE(dd.delta, 0)) OVER (ORDER BY d.day))::bigint AS balance_minor
            FROM days d
            LEFT JOIN daily_delta dd ON dd.day = d.day
            ORDER BY d.day
            """
        ),
        {"g": garage_id, "from_d": from_date, "to_d": to_date},
    )
    outstanding_trend = [
        {"date": str(r.day), "value": int(r.balance_minor)}
        for r in outstanding_result.fetchall()
    ]

    return {
        "from_date": str(from_date),
        "to_date": str(to_date),
        "revenue_trend": revenue_trend,
        "repair_count_trend": repair_count_trend,
        "mechanic_productivity": mechanic_productivity,
        "outstanding_trend": outstanding_trend,
    }


async def invalidate_cache(garage_id: int) -> None:
    try:
        redis = get_redis()
        await redis.delete(f"{_CACHE_KEY_PREFIX}{garage_id}")
    except Exception:
        logger.warning("kpi_cache_invalidate_failed", exc_info=True)
