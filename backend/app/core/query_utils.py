"""Shared query-building helpers for list endpoints (sorting, etc.)."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import Select
from sqlalchemy.sql.elements import ColumnElement


def apply_sort(
    stmt: Select,
    sort_by: Optional[str],
    sort_dir: str,
    sortable_columns: dict[str, ColumnElement],
    default: ColumnElement,
) -> Select:
    """Order `stmt` by a column looked up from `sortable_columns[sort_by]`.

    `sort_by` is validated against the caller-supplied allowlist rather than used
    directly, so an unknown/absent key safely falls back to `default` instead of
    raising or building unsafe SQL from user input.
    """
    column = sortable_columns.get(sort_by) if sort_by else None
    if column is None:
        column = default
    return stmt.order_by(column.desc() if sort_dir == "desc" else column.asc())
