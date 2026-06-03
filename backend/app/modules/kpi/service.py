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


async def _revenue_mtd(db: AsyncSession, garage_id: int) -> tuple[Optional[Decimal], None]:
    row = await db.execute(
        text(
            """
            SELECT COALESCE(SUM(total_minor), 0)
            FROM invoice
            WHERE garage_id = :g
              AND status IN ('issued', 'partial', 'paid')
              AND issued_at >= date_trunc('month', now() AT TIME ZONE 'UTC')
              AND deleted_at IS NULL
            """
        ),
        {"g": garage_id},
    )
    return Decimal(row.scalar() or 0), None


async def _revenue_ytd(db: AsyncSession, garage_id: int) -> tuple[Optional[Decimal], None]:
    row = await db.execute(
        text(
            """
            SELECT COALESCE(SUM(total_minor), 0)
            FROM invoice
            WHERE garage_id = :g
              AND status IN ('issued', 'partial', 'paid')
              AND issued_at >= date_trunc('year', now() AT TIME ZONE 'UTC')
              AND deleted_at IS NULL
            """
        ),
        {"g": garage_id},
    )
    return Decimal(row.scalar() or 0), None


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
    """Total outstanding amount in minor units."""
    row = await db.execute(
        text(
            """
            SELECT COALESCE(SUM(outstanding_minor), 0)
            FROM invoice
            WHERE garage_id = :g
              AND status IN ('issued', 'partial')
              AND deleted_at IS NULL
            """
        ),
        {"g": garage_id},
    )
    return Decimal(row.scalar() or 0), None


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
    revenue_result = await db.execute(
        text(
            """
            SELECT (issued_at AT TIME ZONE 'UTC')::date AS day,
                   COALESCE(SUM(total_minor), 0)::bigint AS amount_minor
            FROM invoice
            WHERE garage_id = :g
              AND status IN ('issued', 'partial', 'paid')
              AND (issued_at AT TIME ZONE 'UTC')::date BETWEEN :from_d AND :to_d
              AND deleted_at IS NULL
            GROUP BY day
            ORDER BY day
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

    return {
        "from_date": str(from_date),
        "to_date": str(to_date),
        "revenue_trend": revenue_trend,
        "repair_count_trend": repair_count_trend,
        "mechanic_productivity": mechanic_productivity,
    }


async def invalidate_cache(garage_id: int) -> None:
    try:
        redis = get_redis()
        await redis.delete(f"{_CACHE_KEY_PREFIX}{garage_id}")
    except Exception:
        logger.warning("kpi_cache_invalidate_failed", exc_info=True)
