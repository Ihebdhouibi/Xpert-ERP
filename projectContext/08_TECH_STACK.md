# 08 — Tech Stack

Mandated by [Context.md](Context.md): **React (frontend), FastAPI (backend), PostgreSQL, Python 3.11.0, PaddleOCR 3.x**. This document fills in the rest of the stack and justifies each choice with pros, cons, and a recommended default.

Per [Context.md](Context.md), every choice with multiple viable options is recorded with pros/cons and an effort estimate. Choices are made now to unblock M0, but each can be revisited at the next major version with explicit migration cost.

---

## 1. Backend runtime

| Choice         | Default                            |
|----------------|------------------------------------|
| Language       | Python **3.11.0** (mandated)       |
| Framework      | **FastAPI** (mandated)             |
| ASGI server    | **Uvicorn** behind Gunicorn workers|
| ORM            | **SQLAlchemy 2.x** with async      |
| Validation     | **Pydantic v2** (FastAPI default)  |
| Migrations     | **Alembic**                        |
| Settings       | **pydantic-settings**              |

### 1.1 ORM choice

- **SQLAlchemy 2.x** (recommended). Pros: mature, async support, rich query builder, used widely with FastAPI. Cons: steeper learning curve than alternatives.
- **SQLModel**: thinner wrapper combining SQLAlchemy + Pydantic. Pros: less boilerplate. Cons: smaller ecosystem, slower release cadence, leaky abstraction at the edges.
- **Tortoise ORM**: async-first, Django-style. Pros: simpler. Cons: smaller community, fewer escape hatches for complex SQL.

Decision: SQLAlchemy 2.x. Effort to swap later: high (estimated 3 PW).

### 1.2 Background job runner

- **Celery + Redis** (recommended). Pros: battle-tested, retries, scheduled tasks via Celery Beat, broad operational knowledge. Cons: heavier infra footprint.
- **APScheduler in-process**. Pros: simplest, no extra service. Cons: not robust to multi-worker, no native retry, fragile under load.
- **RQ + Redis**. Pros: lighter than Celery. Cons: fewer features (no good scheduled-task model), smaller ecosystem.
- **Dramatiq**. Pros: cleaner API than Celery. Cons: smaller community.

Decision: **APScheduler** for M0–M7 (no scheduled triggers heavier than KPI snapshots), **Celery + Redis** introduced at M8 when notifications, OCR queue, and KPI snapshots need durability. Effort to introduce Celery later: 1 PW; doing it at M0 would add ops complexity before it pays off.

### 1.3 PDF generation

- **WeasyPrint** (recommended). Pros: HTML/CSS templates, easy theming, locale-friendly. Cons: heavier dependency, requires system libs (cairo, pango).
- **ReportLab**. Pros: programmatic, full control, lean. Cons: templates are code, harder to theme.
- **Jinja2 + wkhtmltopdf**. Pros: familiar HTML. Cons: wkhtmltopdf development is slow; rendering quirks.

Decision: WeasyPrint. Effort to swap: 1 PW.

### 1.4 Object storage client

- **boto3** for S3-compatible (recommended). Pros: ubiquitous. Cons: heavy dep.
- **minio-py** for MinIO-first. Pros: lighter. Cons: AWS-specific features less polished.

Decision: boto3, configured against MinIO in dev and any S3-compatible service in prod.

### 1.5 OCR

- **PaddleOCR 3.x** (mandated). Pros: strong multilingual support, good on cards/IDs, active maintenance, GPU and CPU paths.
- Wrapped behind an `OcrEngine` interface so a future engine swap is one adapter file. Effort to swap: 1 PW.

### 1.6 Other backend libs

| Concern        | Library                                                  | Notes                                  |
|----------------|----------------------------------------------------------|----------------------------------------|
| Password hash  | argon2-cffi                                              | Argon2id with sensible defaults        |
| JWT            | python-jose or authlib                                   | RS256 or HS256 per deployment          |
| HTTP client    | httpx                                                    | async, used for SMTP/SMS adapters      |
| Excel export   | openpyxl                                                 | accounting export, KPI export          |
| Email          | aiosmtplib + Jinja2 templates                            | adapter interface                      |
| SMS            | provider-specific adapter behind a generic interface     | initial provider TBD per market        |
| Logging        | structlog                                                | JSON output, per-component handlers    |
| Testing        | pytest, pytest-asyncio, pytest-cov                       | see [09_TESTING_STRATEGY.md](09_TESTING_STRATEGY.md) |
| Lint/type      | ruff, mypy                                               | strict mode on for type-safety surface |

---

## 2. Frontend stack

| Choice                  | Default                          |
|-------------------------|----------------------------------|
| Framework               | **React 18+** (mandated)         |
| Language                | **TypeScript 5.x**               |
| Bundler / dev server    | **Vite**                         |
| Routing                 | **React Router 6+**              |
| Server state            | **TanStack Query v5**            |
| Forms                   | **React Hook Form + Zod**        |
| HTTP client             | **Axios** (typed wrapper)        |
| UI component library    | see 2.1 below                    |
| Charts                  | **Recharts** for dashboard       |
| i18n                    | **react-intl** (ICU MessageFormat)|
| Date                    | **date-fns** + **date-fns-tz**    |
| PDF preview             | **react-pdf**                     |
| Tablet/mobile gestures  | **use-gesture** + **framer-motion** (selective) |
| Offline sync (M9)       | **IndexedDB** via Dexie           |

### 2.1 UI component library

- **MUI** (Material UI) (recommended). Pros: large component set, accessibility, theming, French locale support. Cons: bundle size, opinionated look.
- **Mantine**. Pros: modern, comfortable defaults, strong forms. Cons: smaller ecosystem.
- **Chakra UI**. Pros: ergonomic, theming. Cons: less complete data-table story.
- **Ant Design**. Pros: very complete for back-office. Cons: bundle, look feels Chinese-enterprise out of the box.

Decision: MUI for the back-office screens (reception, admin). For the workshop tablet view, a lighter, custom design system built on top of MUI primitives to optimize touch targets and offline UX.

### 2.2 State management beyond TanStack Query

For UI-only state that isn't server-derived, prefer React state and context. Reach for **Zustand** if a feature accumulates more than three context providers; do not introduce Redux unless a measurable need arises.

### 2.3 Data table

- **TanStack Table** + virtualization. Pros: headless, performant, flexible. Cons: requires more wiring.
- MUI's DataGrid (community or pro). Pros: drop-in. Cons: license for pro features.

Decision: TanStack Table + a thin custom wrapper. Pro features behind a feature flag if needed.

---

## 3. Database

| Choice          | Default                              |
|-----------------|--------------------------------------|
| RDBMS           | **PostgreSQL 15+** (mandated)        |
| Extensions      | `citext`, `pg_trgm`, `uuid-ossp` or `pgcrypto`, `unaccent`, `btree_gin` |
| Full-text       | built-in `tsvector` (good enough for v1) |
| Migrations      | Alembic                              |
| Connection pool | pgbouncer in prod                    |
| Backup          | pg_basebackup + WAL archiving        |

### 3.1 Search

Built-in PostgreSQL FTS (`tsvector` + `pg_trgm` for trigram) is sufficient for customer, vehicle, and parts search at the assumed scale (see capacity in [01_SOFTWARE_CONCEPTION.md](01_SOFTWARE_CONCEPTION.md)). A dedicated search engine (Meilisearch, Typesense) is out of scope and can be added later if facets and typo tolerance become a requirement.

---

## 4. Caching and queue

| Choice    | Default               |
|-----------|-----------------------|
| Cache     | **Redis**             |
| Sessions  | Redis (token deny list) |
| Queue     | Redis as Celery broker |

Single Redis instance per deployment is fine for the assumed scale. Cluster mode is not in scope for v1.

---

## 5. Object storage

| Choice       | Default                              |
|--------------|--------------------------------------|
| Dev          | **MinIO** via docker-compose         |
| Prod         | any S3-compatible service            |
| Lifecycle    | transition hot → archive after CFG_PHOTO_ARCHIVE_AFTER_DAYS |
| Encryption   | server-side encryption at rest       |

---

## 6. Observability

| Concern    | Default                                  |
|------------|------------------------------------------|
| Logging    | structlog → JSON Lines → per-component file rotation + stdout. Aggregated by a log shipper (Vector, Fluent Bit, Promtail). |
| Metrics    | Prometheus-compatible `/metrics` from FastAPI; optional in MVP, required at M10. |
| Tracing    | OpenTelemetry, deferred to post-MVP unless needed earlier. |
| Dashboards | Grafana for metrics and logs visualization. |
| Errors     | Sentry (or alternative) for both frontend and backend. |

---

## 7. Security

| Concern              | Default                                              |
|----------------------|------------------------------------------------------|
| TLS                  | Let's Encrypt via reverse proxy                      |
| Secrets              | environment + a secrets manager (Vault, AWS SM, etc.) — never committed |
| CSP                  | strict CSP on the SPA, with reporting endpoint       |
| Dependency scan      | Dependabot or Renovate + pip-audit + npm-audit       |
| Container scan       | Trivy in CI                                          |
| Static analysis      | ruff, bandit, semgrep (selective rules)              |
| 2FA                  | TOTP optional in MVP; mandatory for admin by M12     |

---

## 8. CI/CD

| Stage          | Default                                              |
|----------------|------------------------------------------------------|
| CI             | GitHub Actions or GitLab CI (depending on hosting)   |
| Container build| multi-stage Dockerfile per service                   |
| Registry       | per host (GHCR, GitLab Registry, ECR)                |
| Deployment     | docker-compose for single-host, k8s manifests provided in `infra/k8s/` |
| IaC            | Terraform optional, introduced when cloud usage grows|

See [10_DEPLOYMENT_DEVOPS.md](10_DEPLOYMENT_DEVOPS.md) for the pipeline shape.

---

## 9. Containerization

- **Docker** required for every service; **docker-compose** for local stack.
- Each service: alpine or debian-slim base; non-root user; minimal layers.
- Build args: `APP_VERSION`, `GIT_SHA`. Exposed in `/health` and in logs.

---

## 10. Code style and tooling

| Layer    | Tools                                                          |
|----------|----------------------------------------------------------------|
| Python   | ruff (lint + format), mypy (strict on type-safety zones), pyright (optional), pytest with coverage. |
| TS/React | eslint (typescript-eslint), prettier, tsc strict, vitest, react-testing-library, playwright for e2e. |
| Hooks    | pre-commit for lint and format; commit-msg lints conform to git conventions in [Context.md](Context.md). |

---

## 11. Effort comparison summary

This table summarizes each non-mandated choice with rough swap effort if changed later. Use it when revisiting decisions at v2.

| Decision area      | Default               | Effort to swap |
|--------------------|-----------------------|----------------|
| ORM                | SQLAlchemy 2.x        | 3 PW           |
| Background runner  | APScheduler → Celery  | 1 PW (already planned) |
| PDF                | WeasyPrint            | 1 PW           |
| OCR                | PaddleOCR             | 1 PW           |
| UI library         | MUI                   | 2–3 PW         |
| Data table         | TanStack Table        | 1 PW           |
| Charts             | Recharts              | 0.5 PW         |
| Object storage     | S3-compatible         | 0.5 PW         |
| Email/SMS adapter  | provider-specific     | 0.5 PW per provider |
