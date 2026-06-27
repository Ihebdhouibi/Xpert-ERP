# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Xpert-ERP is a garage management system (French locale) with a FastAPI backend and React/TypeScript frontend. It handles repair orders, invoicing, stock, purchasing, customer credit limits, and accounting exports.

## Commands

### Backend

```bash
cd backend

# Dev server
uvicorn app.main:app --reload

# Run all tests
pytest

# Run a single test file or test
pytest tests/test_auth_endpoints.py
pytest tests/test_auth_endpoints.py::test_login

# Migrations
alembic upgrade head
alembic current
alembic revision -m "description"  # create new migration
```

### Frontend

```bash
cd frontend

npm run dev           # Vite dev server → http://localhost:5173
npm run type-check    # tsc --noEmit (use this before committing)
npm run lint          # ESLint, zero warnings allowed
npm run build         # tsc -b && vite build
```

> **Known quirk:** if `tsc --noEmit` fails with a deprecation error, use `tsc --noEmit --ignoreDeprecations 5.0`.

### Infrastructure

```bash
cd infra && docker-compose up -d   # PostgreSQL 5433, Redis 6379, MinIO 9000/9001
```

## Architecture

### Backend module layout

Every business module under `backend/app/modules/<name>/` follows the same pattern:

```
router.py      FastAPI endpoints + permission guards
service.py     Business logic (the real code lives here)
repository.py  Raw DB queries (select/insert/update)
schemas.py     Pydantic request & response models
models.py      SQLAlchemy ORM models
```

Modules: `auth`, `rbac`, `customer`, `vehicle`, `repair_order`, `inspection`, `invoice`, `quotation`, `delivery_note`, `credit_note`, `advance_payment`, `payment`, `cash_session`, `purchase_order`, `supplier`, `supplier_invoice`, `bon_de_retour`, `supplier_credit_note`, `parts`, `stock`, `media`, `documents`, `ocr`, `pdf`, `notification`, `kpi`, `accounting_export`, `sequence`, `audit`, `config`.

### Auth & RBAC

- JWT access + refresh tokens. Permissions are **baked into the JWT at login time**. After any role/permission change, affected users must log out and log back in.
- `require_permission("code")` FastAPI dependency guards endpoints. The permission catalog is the source of truth in `backend/app/modules/rbac/permissions.py`.
- Permission codes follow `<resource>.<action>` (e.g. `invoice.issue`, `repair_order.transition`).
- System roles: `super_admin`, `admin`, `receptionist`, `mechanic`, `inventory_manager`, `accountant`, `read_only`. The `receptionist` role (DB code: `receptionist`, display: "Réceptionniste") has full operational access minus Administration and credit override approval.
- Frontend `SYSTEM_ROLES` array in `frontend/src/pages/admin/UsersPage.tsx` is hardcoded with role codes — these must match the DB role codes exactly.

### Money & balances

All monetary values are stored in **minor units (cents)** — `total_minor`, `outstanding_minor`, `credit_limit_minor`, etc. Display conversion: divide by 100.

Customer outstanding balance is maintained via an **append-only ledger** (`customer_balance_event` table) with a denormalised snapshot in `customer.outstanding_minor`. Never update/delete ledger rows; always use `post_balance_event()` in `credit_service.py`.

### Credit limit enforcement

`check_credit_limit()` in `backend/app/modules/customer/credit_service.py` is called at BL and invoice issue time. It returns `True` if the operation passed via an admin-approved override (important: the caller uses this to set `issued_under_override` on the delivery note). When a BL is issued under an override and later converted to an invoice, the invoice credit check is skipped — the approval travels with the document via `delivery_note.issued_under_override`.

### Frontend routing & nav

- `frontend/src/router.tsx` — React Router 6 route tree.
- `frontend/src/components/layout/navConfig.ts` — sidebar nav items, each optionally guarded by a `permission` field. Items only render if the logged-in user holds that permission.
- API calls are made via per-module `*Api.ts` files in `frontend/src/lib/`, all using the shared `apiClient.ts` Axios instance (handles token attachment and 401 refresh).

### Notification system

`AppNotification` model with a 30-second polling loop on the frontend. `create_app_notification()` in `notification/inbox_router.py` creates in-app notifications. Notification triggers are seeded via `notification/templates_seed.py`.

## Alembic migration conventions

- **Never use `op.create_table()` with SQLAlchemy `Enum` types** — SQLAlchemy re-emits `CREATE TYPE` and causes `DuplicateObjectError`. Instead, create enums and tables with raw SQL via `op.execute()`.
- Idempotent enum creation pattern:
  ```python
  op.execute("""
      DO $$ BEGIN
          CREATE TYPE my_enum AS ENUM ('a', 'b');
      EXCEPTION WHEN duplicate_object THEN NULL;
      END $$;
  """)
  ```
- Use `CREATE TABLE IF NOT EXISTS` and `INSERT ... ON CONFLICT DO NOTHING` (where a unique constraint exists) or `INSERT ... WHERE NOT EXISTS (...)` (when no unique constraint) for idempotency.
- The `role` table has no unique constraint on `code` — use `WHERE NOT EXISTS` not `ON CONFLICT (code)`.
- Migration files live in `backend/migrations/versions/` numbered `NNNN_description.py`.

## Environment

Backend reads config from `.env` (see `.env.example`). Key vars: `DATABASE_URL` (asyncpg), `REDIS_URL`, `SECRET_KEY`, `S3_*` (MinIO), `CREDIT_LIMIT_MODE` (`block` or `warn`).

Frontend reads `VITE_API_BASE_URL` and `VITE_GARAGE_ID` from `.env`.
