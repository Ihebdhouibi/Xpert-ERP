"""Cross-dialect SQLAlchemy custom types.

These types select the best native implementation per dialect and fall back
to a portable equivalent on other engines (e.g. SQLite for testing).
"""
from __future__ import annotations

from sqlalchemy import BigInteger, Integer, Text
from sqlalchemy.types import TypeDecorator

# ---------------------------------------------------------------------------
# BigIntPK — BIGINT on PostgreSQL, INTEGER on SQLite (required for rowid
# auto-increment; SQLite only treats exactly "INTEGER PRIMARY KEY" as rowid).
# ---------------------------------------------------------------------------
BigIntPK = BigInteger().with_variant(Integer(), "sqlite")


class CIText(TypeDecorator):
    """Case-insensitive text.

    - PostgreSQL → native ``CITEXT`` extension type.
    - All other dialects (SQLite, etc.) → ``Text`` with lowercasing applied
      on the Python side so that case-insensitive semantics are preserved in
      unit / integration tests that run against an in-memory SQLite engine.
    """

    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect):  # type: ignore[override]
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import CITEXT

            return dialect.type_descriptor(CITEXT())
        return dialect.type_descriptor(Text())

    def process_bind_param(self, value, dialect):  # type: ignore[override]
        """Lowercase on non-PG dialects to emulate case-insensitivity."""
        if value is not None and dialect.name != "postgresql":
            return value.lower()
        return value


class JsonB(TypeDecorator):
    """JSON column.

    - PostgreSQL → native ``JSONB`` for indexable binary JSON.
    - All other dialects → ``Text`` storing JSON as a string (tests only).
    """

    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect):  # type: ignore[override]
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import JSONB

            return dialect.type_descriptor(JSONB())
        from sqlalchemy import JSON

        return dialect.type_descriptor(JSON())

    def process_bind_param(self, value, dialect):  # type: ignore[override]
        return value

    def process_result_value(self, value, dialect):  # type: ignore[override]
        return value
