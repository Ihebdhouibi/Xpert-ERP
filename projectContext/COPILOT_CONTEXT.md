# COPILOT CONTEXT — Xpert-ERP Garage Management System

This file is the authoritative reference for GitHub Copilot to stay aligned with all project requirements, conventions, and constraints at all times. Read this before every implementation task.

---

## 1. Project Identity

**Name:** Xpert-ERP  
**Type:** Web-based Garage / Dealer Management System (GMS/DMS)  
**Purpose:** Centralize and automate all operations of an automotive repair workshop — workshop, invoicing, inventory, CRM, finance, reporting, document archival.  
**Primary language:** French (UI strings externalized for future locale switching)  
**Deployment:** Single-garage for MVP; multi-garage architecture introduced in Phase 12 but `garage_id` column is present in every primary table from day one.

---

## 2. Non-Negotiable Rules

These apply to every line of code, forever.

| Rule | Detail |
|------|--------|
| No hard-coded values | Every threshold, rate, format, delay, window, or limit is configuration (env or `settings` DB table, prefixed `CFG_`) |
| No emojis | Strictly forbidden in code, logs, templates, or UI strings |
| Production-ready from day one | No throwaway code merged to `main`; `stable-testing` receives only verified-stable versions |
| Per-component logging | Each module (`auth`, `customer`, `repair_order`, `inventory`, `invoice`, `payment`, `ocr`, etc.) writes to its own structured log file via `structlog` |
| Edge cases are part of the feature | A feature is incomplete without explicit handling of empty state, concurrent edit, partial failure, network loss, missing data |
| All money is integer minor-units | `BIGINT` in DB (cents/centimes), never `FLOAT`; VAT computed on totals with banker's rounding |
| Soft delete | Operational entities are soft-deleted; purged after configurable retention window |
| Optimistic concurrency | `version` column + `If-Match` on repair orders, quotations, invoices, stock movements; concurrent edits return 409 |
| Document numbers monotonic and gap-free | Issued by a dedicated `document_sequence` service with transactional lock; never `MAX(id)+1` |
| Auditability | Every sensitive action writes to `audit_log` with `user_id`, `timestamp`, `old_value`, `new_value`, `reason` |
| Tenancy-ready | All primary tables carry `garage_id`; all queries filter by it from day one |
| OWASP ASVS Level 2 | Argon2id passwords, JWT/session with rotation, rate limiting, input validation, no SQL injection |

---

## 3. Tech Stack (Mandated)

### Backend
| Concern | Choice |
|---------|--------|
| Language | Python 3.11.0 |
| Framework | FastAPI |
| ASGI | Uvicorn behind Gunicorn |
| ORM | SQLAlchemy 2.x async |
| Validation | Pydantic v2 |
| Migrations | Alembic |
| Settings | pydantic-settings |
| Password hashing | argon2-cffi (Argon2id) |
| JWT | python-jose or authlib (RS256 / HS256) |
| Logging | structlog (JSON, per-component file handlers) |
| Background jobs | APScheduler (M0–M7), Celery + Redis (from M8) |
| PDF generation | WeasyPrint |
| OCR | PaddleOCR 3.x (wrapped behind `OcrEngine` interface) |
| Object storage client | boto3 (MinIO in dev, S3-compatible in prod) |
| HTTP client | httpx (async) |
| Email | aiosmtplib + Jinja2 templates |
| Excel export | openpyxl |
| Testing | pytest, pytest-asyncio, pytest-cov |
| Lint / type-check | ruff, mypy (strict) |

### Frontend
| Concern | Choice |
|---------|--------|
| Framework | React 18+ |
| Language | TypeScript 5.x |
| Bundler | Vite |
| Routing | React Router 6+ |
| Server state | TanStack Query v5 |
| Forms | React Hook Form + Zod |
| HTTP client | Axios (typed wrapper) |
| UI components | MUI (back-office); custom MUI-based for tablet/workshop |
| Charts | Recharts |
| i18n | react-intl (ICU MessageFormat) |
| Date/time | date-fns + date-fns-tz |
| PDF preview | react-pdf |
| Offline sync | IndexedDB via Dexie (M9) |

### Infrastructure
| Concern | Choice |
|---------|--------|
| Database | PostgreSQL 15+ |
| Cache / queue broker | Redis |
| Object storage | MinIO (dev), S3-compatible (prod) |
| Static serving | Nginx (also TLS termination and API reverse proxy) |
| Containerization | Docker + docker-compose (dev), container-based prod |
| CI/CD | GitHub Actions (lint, type-check, unit tests, build on every PR) |

---

## 4. Architecture

**Pattern:** Modular monolith — one FastAPI process, modules as packages. Each module has `router`, `service`, `repository`, `schemas`, `tests`. Modules communicate only through service interfaces, never via cross-module SQL joins.

**Frontend:** Single React SPA, route-split per module.

**Backend modules:**
`auth`, `rbac`, `customer`, `vehicle`, `repair_order`, `inspection`, `workshop`, `inventory`, `quotation`, `invoice`, `payment`, `cash_register`, `supplier`, `purchase_order`, `notification`, `document`, `ocr`, `reporting`, `audit`, `config`

---

## 5. User Roles (RBAC)

| Role | Key capabilities |
|------|-----------------|
| `super_admin` | Cross-garage platform management only |
| `admin` | All modules + user management + garage settings + security |
| `secretary` | CRM, quotations, invoices, cash register, suppliers, scheduling |
| `mechanic` | Workshop operations, inspection, status updates, time tracking, media upload |
| `inventory_manager` | Parts catalog, stock movements, purchase reception, low-stock alerts |
| `accountant` | Finance read + accounting export |
| `read_only` | Read-only across all modules (auditors, trainees) |

Users may hold multiple roles; effective permissions are the union.

---

## 6. Project Phases (Delivery Order)

| Phase | Name | Key modules | Effort (PW) |
|-------|------|-------------|-------------|
| M0 | Foundations | Repo, CI/CD, DB skeleton, logging, config, base UI | 3 |
| M1 | Auth and RBAC | User, Role, Permission, Audit log, Login UI | 3 |
| M2 | Customer and Vehicle | Customer CRM, Vehicle records, document upload entry point | 4 |
| M3 | Repair Order and Workshop | Repair Order lifecycle, mechanic assignment, kanban, time tracking, photos | 5 |
| M4 | Inventory and Stock | Parts catalog, stock movements, reservations, low-stock alerts | 4 |
| M5 | Quotation and Invoice | Quotation, Invoice, VAT engine, discount engine, PDF, document numbering | 5 |
| M6 | Finance and Cash Register | Payments, partial payments, deposits, cash closing, Z-report | 4 |
| **MVP boundary above** | | | |
| M7 | Suppliers and Purchasing | Supplier CRUD, RFQ, PO, reception, supplier invoice, price history | 4 |
| M8 | Notifications and Reminders | SMS/email adapters, template editor, scheduled reminders, delivery log | 3 |
| M9 | Digital Inspection and Media | Checklist templates, tablet inspection, photo/video, PDF report, approval link | 3 |
| M10 | Reporting and Analytics | KPI dashboard, CSV/Excel export, accounting export, scheduled snapshots | 4 |
| M11 | Document Management and OCR | GED categories, object storage lifecycle, PaddleOCR pipeline for carte grise / ID | 4 |
| M12 | Multi-garage and Hardening | Garage tenancy, row-level filtering audit, perf hardening, security audit, load test | 4 |

**Total:** 50 PW solo; ~30–34 calendar weeks with two engineers from M2 onward.

---

## 7. Git Conventions

- `Feat (Feature name): description #<GitHub issue ID>` — new features (request issue ID if not provided)
- `Chore (name): description` — medium changes, config, tooling
- `test: description` — test-only commits
- `Perf: description` — performance improvements
- `Docs: description` — documentation

**Branches:**
- `main` — integration branch for current development
- `stable-testing` — stable versions only (48h soak, no critical defects)
- `feature/<name>` — feature branches, never merged without CI green + PR review

---

## 8. Documentation Conventions

After every implemented and tested feature:
- Create `docs/feature/<featureName>/README.md` (or create the folder if it does not exist)
- Store test results in `docs/tests/testFor<FeatureName>/`
- Store bug investigation logs in `docs/bugs/bug<ID>/`

---

## 9. Out of Scope (Do Not Implement)

- Native iOS / Android apps (web responsive for tablet only)
- OBD-II / scanner telemetry integration
- Customer-facing public portal beyond notification emails / SMS and quotation approval links
- Full accounting / bookkeeping (system exports to accounting software, does not replace it)
- Marketing automation beyond segmentation and templated bulk email/SMS
- Tax filing

---

## 10. Key Domain Constraints

- **Repair Order status machine:** `created → diagnosis → in_repair → finished → delivered`, optional `paused_waiting_parts`, `paused_waiting_approval`. Illegal transitions return HTTP 422.
- **Stock:** Cannot go negative without an explicit override + audit entry.
- **Invoice:** Cannot be modified after accounting export; only via credit note.
- **Cash session:** Once closed and exported, records are locked.
- **OCR:** Below-threshold extractions NEVER auto-write; always require human confirmation.
- **Document numbers:** Monotonic, gap-free, per type, per year, per garage, issued transactionally.
- **Notifications:** Never sent during configured quiet hours (`CFG_QUIET_HOURS_*`).
- **Security:** Brute-force lockout on login; no auth bypass on protected routes; in-flight tokens denied via Redis deny-list on deactivation.

---

## 11. Performance Targets

- Typical interactive request: < 2s p95
- Search (customer, vehicle, parts): < 300ms p95 at target data volume
- KPI recompute: < 5s at target data volume
- 1,000 stock movements processed: < 10s
- Availability: 99.5% monthly (single-garage)
- Concurrent users: 10 typical, 25 peak

---

## 12. Capacity Assumptions

- 30 active repair orders / day
- 300 invoices / month
- 2,000 customers, 5,000 vehicles, 20,000 part SKUs
- 200,000 stock movements / year
- Photo/video: up to 1 GB per repair order, archived to object storage after `CFG_PHOTO_ARCHIVE_AFTER_DAYS`

---

## 13. Workspace File References

| File | Purpose |
|------|---------|
| `projectContext/00_PLAN_OF_EXECUTION.md` | Master roadmap and phase sequence |
| `projectContext/01_SOFTWARE_CONCEPTION.md` | Design principles and domain model |
| `projectContext/02_MILESTONES.md` | Per-milestone scope, deliverables, exit criteria |
| `projectContext/03_ARCHITECTURE.md` | C4 diagrams (context, container, component) |
| `projectContext/04_DATABASE_DESIGN.md` | Full ERD |
| `projectContext/05_API_DESIGN.md` | REST API conventions |
| `projectContext/06_RBAC_DESIGN.md` | Full permission catalog and role matrix |
| `projectContext/07_MODULE_BREAKDOWN.md` | Per-module scope, entities, edge cases |
| `projectContext/08_TECH_STACK.md` | Full tech stack with rationale |
| `projectContext/09_TESTING_STRATEGY.md` | Test levels, coverage thresholds |
| `projectContext/10_DEPLOYMENT_DEVOPS.md` | CI/CD, Docker, deployment guide |
| `projectContext/diagrams/` | ERDs, flowcharts, sequence, state, system diagrams |
| `projectContext/Context.md` | Developer ground rules and coding conventions |
