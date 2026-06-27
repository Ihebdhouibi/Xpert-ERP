# Xpert-ERP — Infrastructure Documentation

> **Purpose:** Production deployment planning reference.  
> **Date:** 2026-06-27  
> **Status:** Active development — branch `integration/frontend-merge`

---

## 1. Project Overview

**Xpert-ERP** is a full-stack Garage Management System (DMS/GMS) for automotive repair workshops.  
It covers: workshop workflow, invoicing, inventory, customer CRM, finance, accounting exports, and analytics.

**Repository root:** `d:\Projects\Xpert-ERP`  
**App version:** 0.1.0  
**DB migrations:** 47 Alembic versions

---

## 2. Repository Layout

```
Xpert-ERP/
├── .env                        # Active secrets (never commit)
├── .env.example                # Template (commit this)
├── backend/                    # FastAPI application
│   ├── app/
│   │   ├── main.py             # App factory + lifespan hooks
│   │   ├── core/               # config, database, redis, logging, middleware
│   │   └── modules/            # 30+ domain modules (auth, invoice, stock, …)
│   ├── migrations/             # Alembic versions (47 total)
│   ├── tests/
│   ├── assets/                 # Logo, static files
│   ├── logs/                   # Rotating log files
│   ├── templates/              # Jinja2 email templates
│   ├── pyproject.toml
│   └── alembic.ini
├── frontend/                   # React + TypeScript
│   ├── src/
│   ├── dist/                   # Production build output
│   ├── package.json
│   └── vite.config.ts          # Vite + PWA config
├── infra/                      # Docker + deployment
│   ├── docker-compose.yml      # 6 services
│   ├── Dockerfile.backend      # Python 3.11 / FastAPI image
│   ├── Dockerfile.backup       # pg_dump + MinIO client image
│   └── scripts/
│       ├── backup.sh           # Daily backup (pg_dump + MinIO mirror + WAL)
│       ├── restore.sh          # Restore from backup
│       └── pitr_basebackup.sh  # Weekly PITR base backup
├── .github/
│   └── workflows/ci.yml        # GitHub Actions CI
├── docs/
│   └── operations/runbook.md   # Operator runbook (startup / backup / restore)
└── projectContext/
    └── ExplainProject.txt      # Business requirements
```

---

## 3. Backend — FastAPI

### Stack

| Item | Version |
|------|---------|
| Python | 3.11.x |
| FastAPI | 0.136.3 |
| Dev server | Uvicorn 0.34.3 |
| Prod server | Gunicorn 23.0.0 + UvicornWorker |
| ORM | SQLAlchemy 2.0.41 (async) |
| DB driver | asyncpg 0.30.0 |
| Migrations | Alembic 1.15.2 |
| Validation | Pydantic 2.11.4 |
| Auth | PyJWT 2.13.0 + Argon2-cffi 23.1.0 |
| PDF | WeasyPrint 68.0 |
| OCR | PaddleOCR 3.0.1 + PaddlePaddle 3.0.0 + OpenCV 4.10.0.84 |
| S3 client | boto3 1.38.18 |
| Job scheduler | APScheduler 3.11.0 |
| Email | aiosmtplib 3.0.2 |
| Logging | structlog 25.3.0 |

### Entry point

```
Module:  app.main:app
Port:    8000
Base URL: /api/v1/*
```

### Startup commands

**Development (local):**
```bash
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --log-config uvicorn_log_config.json
```

**Production (Docker / Gunicorn):**
```bash
gunicorn app.main:app -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000 --workers 2
```

### Lifespan hooks (run automatically on app start)

1. Configure structlog → `logs/` directory
2. **Run `alembic upgrade head`** (auto-migrates DB on every start)
3. Start APScheduler: media archiver, document archiver, notification scheduler
4. Seed notification templates (idempotent)

On shutdown: APScheduler stop → Redis pool close.

### Domain modules (30+)

| Module | Purpose | Prefix |
|--------|---------|--------|
| auth | JWT login / refresh / logout | /auth |
| rbac | Users & roles | /users |
| health | Health check | /health |
| customer | Customer CRM | /customers |
| vehicles | Vehicle records | /vehicles |
| repair_order | RO workflow | /repair-orders |
| parts | Parts catalog | /parts |
| stock | Inventory movements | /stock |
| quotation | Quotations | /quotations |
| invoice | Customer invoices | /invoices |
| payment | Payments | /payments |
| advance_payment | Deposits/prepayments | /advance-payments |
| supplier | Suppliers | /suppliers |
| purchase_order | PO workflow | /purchase-orders |
| supplier_invoice | Supplier invoices | /supplier-invoices |
| cash_session | Cash register | /cash-sessions |
| credit_note | Credit notes & refunds | /credit-notes |
| bon_de_retour | Return orders | /bon-de-retours |
| pdf | PDF generation | /pdf |
| inspection | Vehicle inspections | /inspections |
| media | Photo/video upload (S3) | /media |
| documents | Document archive (S3) | /documents |
| kpi | Analytics & dashboards | /kpi |
| notification | Email/SMS scheduling | /notifications |
| ocr | Document OCR | /ocr |
| accounting_export | Accounting export (CSV ZIP) | /accounting |
| delivery_note | Delivery documents | /delivery-notes |
| sequence | Document numbering | /sequences |
| config | Runtime CFG_* settings | /config |
| logs | Log file viewer | /logs |
| audit | Audit trail (internal only) | — |

---

## 4. Frontend — React + TypeScript

### Stack

| Item | Version |
|------|---------|
| React | 18.3.1 |
| TypeScript | 5.7.2 |
| Build tool | Vite 6.2.0 |
| Styling | Material-UI 5.16.14 + Emotion |
| Forms | React Hook Form 7.54.2 + Zod 3.24.1 |
| Data fetching | TanStack React Query 5.67.0 |
| Routing | React Router DOM 6.28.2 |
| Charts | Recharts 2.15.0 |
| i18n | react-intl 6.8.7 |
| PWA | vite-plugin-pwa 1.3.0 |

### Ports

| Mode | Port |
|------|------|
| Development (Vite dev server) | **5173** |
| Production | Served from `dist/` behind reverse proxy (80/443) |

### Commands

```bash
cd frontend
npm install

# Development
npm run dev          # Starts Vite on :5173

# Production build
npm run build        # Outputs to frontend/dist/

# Quality checks
npm run type-check   # tsc --noEmit
npm run lint         # ESLint
```

### Environment file

`frontend/.env` (copy from `.env.example`):
```
VITE_API_BASE_URL=http://localhost:8000
VITE_GARAGE_ID=1
```

In production set `VITE_API_BASE_URL` to the public API URL before building.

### PWA

- Service Worker caches app shell (JS, CSS, HTML, fonts)
- API calls: NetworkFirst, 5 s timeout, 24 h expiry
- Installable as standalone app
- Start URL: `/tablet` (mechanic tablet interface)

---

## 5. Docker Infrastructure

### Compose file

`infra/docker-compose.yml` — **6 services**

All services use JSON log driver (`max-size: 10m`, `max-file: 5`).

---

### Service: db (PostgreSQL)

```yaml
image:          postgres:15-alpine
container_name: xpert_erp_db
ports:          5433:5432  (host:container)
restart:        unless-stopped
healthcheck:    pg_isready every 10 s
volumes:
  - pg_data:/var/lib/postgresql/data
  - pg_wal_archive:/var/lib/postgresql/wal_archive
env:
  POSTGRES_USER:     xpert (or $POSTGRES_USER)
  POSTGRES_PASSWORD: <from .env>
  POSTGRES_DB:       xpert_erp
WAL:
  wal_level=replica, archive_mode=on, max_wal_senders=3, wal_keep_size=128
```

> **Note:** In the current docker-compose the API container connects to the host PostgreSQL via `host.docker.internal`, not the containerized `db` service. For production this should be unified (see checklist §9).

---

### Service: redis

```yaml
image:          redis:7-alpine
container_name: xpert_erp_redis
ports:          6379:6379
restart:        unless-stopped
healthcheck:    redis-cli ping every 10 s
volumes:
  - redis_data:/data
command:        redis-server --requirepass <REDIS_PASSWORD>
```

---

### Service: mailpit (dev only)

```yaml
image:          axllent/mailpit:latest
container_name: xpert_erp_mailpit
ports:
  - 1025:1025   (SMTP)
  - 8025:8025   (Web UI — view emails at http://localhost:8025)
restart:        unless-stopped
```

Replace with a real SMTP relay in production.

---

### Service: minio (S3-compatible storage)

```yaml
image:          minio/minio:latest
container_name: xpert_erp_minio
ports:
  - 9000:9000   (API)
  - 9001:9001   (Console — http://localhost:9001)
restart:        unless-stopped
healthcheck:    mc ready every 10 s
volumes:
  - minio_data:/data
command:        server /data --console-address ":9001"
env:
  MINIO_ROOT_USER:     minio_admin
  MINIO_ROOT_PASSWORD: <from .env>
buckets (created by app):
  xpert-documents
  xpert-media
  xpert-backups
```

In production, replace with AWS S3 (or a dedicated MinIO cluster). Update `S3_ENDPOINT_URL`, `S3_PUBLIC_ENDPOINT_URL`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`.

---

### Service: api (FastAPI backend)

```yaml
build:
  context: ../backend
  dockerfile: ../infra/Dockerfile.backend
container_name: xpert_erp_api
ports:          8000:8000
restart:        unless-stopped
depends_on:     redis (healthy), minio (healthy), mailpit (started)
env_file:       ../.env
env overrides:
  DATABASE_URL:        postgresql+asyncpg://xpert:<pw>@host.docker.internal:5432/xpert_erp
  REDIS_URL:           redis://:<pw>@redis:6379/0
  S3_ENDPOINT_URL:     http://minio:9000
  S3_PUBLIC_ENDPOINT_URL: http://localhost:9000
  SMTP_HOST:           mailpit
  SMTP_PORT:           1025
  SMTP_USE_TLS:        false
  PDF_GARAGE_LOGO_PATH: /app/assets/logo.png
volumes:
  - ../backend:/app    (live-reload mount — remove in production)
  - ../logs:/app/logs
command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --log-config uvicorn_log_config.json
```

**Production change:** replace `--reload` with Gunicorn workers and remove the code bind-mount.

---

### Service: backup (profile: `backup`)

```yaml
build:          infra/ + Dockerfile.backup
container_name: xpert_erp_backup
profile:        backup  (not started by default)
depends_on:     db (healthy)
entrypoint:     /bin/bash /scripts/backup.sh
volumes:
  - ../infra/scripts:/scripts:ro
  - pg_wal_archive:/var/lib/postgresql/wal_archive:ro
```

Run manually or via cron (see §8).

---

### Dockerfile.backend (`infra/Dockerfile.backend`)

```dockerfile
FROM python:3.11-slim
WORKDIR /app
RUN apt-get install -y \
    build-essential libpq-dev libcairo2 libpango-1.0-0 \
    libgdk-pixbuf-xlib-2.0-0 libffi-dev shared-mime-types \
    fonts-liberation fonts-dejavu-core libgl1 libglib2.0-0
COPY pyproject.toml .
RUN pip install -e ".[dev]"
COPY . .
EXPOSE 8000
CMD ["gunicorn", "app.main:app", "-k", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", "--workers", "2"]
```

System libs required for: WeasyPrint (PDF), PaddleOCR, OpenCV, Pillow.

---

### Docker volumes

| Volume | Contents |
|--------|----------|
| `pg_data` | PostgreSQL data directory |
| `pg_wal_archive` | PostgreSQL WAL archive (PITR) |
| `redis_data` | Redis persistence |
| `minio_data` | MinIO object storage |

---

## 6. Environment Variables

Master file: `.env` (root of repo). Copy from `.env.example`.

### Infrastructure

| Variable | Purpose | Dev default |
|----------|---------|-------------|
| `ENVIRONMENT` | dev / staging / production | `development` |
| `DEBUG` | Enable debug mode | `true` |
| `APP_VERSION` | Semver | `0.1.0` |
| `DATABASE_URL` | Async SQLAlchemy URI | `postgresql+asyncpg://xpert:…@localhost:5432/xpert_erp` |
| `DATABASE_ECHO` | Log all SQL | `false` |
| `DATABASE_POOL_SIZE` | Connection pool | `10` |
| `DATABASE_MAX_OVERFLOW` | Overflow connections | `20` |
| `POSTGRES_USER` | DB username (compose) | `xpert` |
| `POSTGRES_PASSWORD` | DB password (compose) | *(required)* |
| `POSTGRES_DB` | DB name (compose) | `xpert_erp` |
| `REDIS_URL` | Redis URI | `redis://:…@localhost:6379/0` |
| `REDIS_PASSWORD` | Redis auth | *(required)* |

### Object Storage (S3 / MinIO)

| Variable | Purpose | Dev default |
|----------|---------|-------------|
| `S3_ENDPOINT_URL` | Internal endpoint | `http://localhost:9000` |
| `S3_PUBLIC_ENDPOINT_URL` | Browser-facing endpoint (presigned URLs) | falls back to `S3_ENDPOINT_URL` |
| `S3_ACCESS_KEY_ID` | Access key | `minio_admin` |
| `S3_SECRET_ACCESS_KEY` | Secret key | *(required)* |
| `S3_BUCKET_DOCUMENTS` | GED bucket | `xpert-documents` |
| `S3_BUCKET_MEDIA` | Photos/videos bucket | `xpert-media` |
| `S3_REGION` | Region | `us-east-1` |
| `SIGNED_URL_EXPIRY_SECONDS` | Presigned URL TTL | `3600` |

### Security & Auth

| Variable | Purpose | Dev default |
|----------|---------|-------------|
| `SECRET_KEY` | JWT signing key (64-byte hex) | *(required — generate fresh for prod)* |
| `ALGORITHM` | JWT algorithm | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token TTL | `30` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Refresh TTL | `7` |
| `ALLOWED_ORIGINS` | CORS allowlist (JSON array) | `["http://localhost:5173"]` |
| `AUTH_MAX_FAILED_ATTEMPTS` | Login retry limit | `5` |
| `AUTH_LOCKOUT_MINUTES` | Lockout duration | `15` |
| `PASSWORD_MIN_LENGTH` | Min password length | `12` |

### Email / SMTP

| Variable | Purpose | Dev default |
|----------|---------|-------------|
| `SMTP_HOST` | Mail server | *(empty → Mailpit on `localhost`)* |
| `SMTP_PORT` | Mail port | `587` |
| `SMTP_USERNAME` | Auth user | *(empty)* |
| `SMTP_PASSWORD` | Auth password | *(empty)* |
| `SMTP_USE_TLS` | Enable TLS | `true` |
| `SMTP_FROM_ADDRESS` | From address | `noreply@xpert-erp.local` |
| `SMTP_FROM_NAME` | From display name | `Xpert-ERP` |
| `FRONTEND_BASE_URL` | Link base for emails | `http://localhost:5173` |

### PDF

| Variable | Purpose | Dev default |
|----------|---------|-------------|
| `PDF_GARAGE_NAME` | Garage name on documents | `Xpert Garage` |
| `PDF_GARAGE_ADDRESS` | Address on documents | *(optional)* |
| `PDF_GARAGE_PHONE` | Phone on documents | *(optional)* |
| `PDF_GARAGE_EMAIL` | Email on documents | *(optional)* |
| `PDF_GARAGE_LOGO_PATH` | Absolute path to logo PNG | `/app/assets/logo.png` (Docker) |
| `PDF_VAT_NUMBER` | VAT number | *(optional)* |
| `PDF_CURRENCY_SYMBOL` | Currency | `€` |
| `PDF_PAYMENT_TERMS` | Payment terms text | `Paiement à 30 jours` |

### Logging

| Variable | Purpose | Dev default |
|----------|---------|-------------|
| `LOG_LEVEL` | `DEBUG`/`INFO`/`WARNING`/`ERROR` | `INFO` |
| `LOG_DIR` | Log directory | `logs` |
| `LOG_MAX_BYTES` | Rotation size | `10485760` (10 MB) |
| `LOG_BACKUP_COUNT` | Rotated file count | `5` |

### Backup

| Variable | Purpose |
|----------|---------|
| `BACKUP_S3_BUCKET` | Backup bucket name |
| `BACKUP_S3_ENDPOINT` | Backup S3 endpoint (can be AWS or MinIO) |
| `BACKUP_S3_ACCESS_KEY` | Backup access key |
| `BACKUP_S3_SECRET_KEY` | Backup secret key |
| `BACKUP_RETENTION_DAYS` | Days to keep dumps |
| `POSTGRES_HOST` | DB hostname used by backup scripts |

### Runtime CFG_* settings (DB-backed, changeable without redeploy)

| Variable | Purpose | Default |
|----------|---------|---------|
| `CFG_GARAGE_NAME` | Garage display name | `Xpert Garage` |
| `CFG_ALLOW_NEGATIVE_STOCK` | Allow negative inventory | `false` |
| `CFG_PO_MATCH_TOLERANCE_PERCENT` | 3-way match tolerance | `5.0` |
| `CFG_KPI_REFRESH_INTERVAL_SECONDS` | KPI cache TTL | `300` |
| `CFG_KPI_WORKSHOP_CAPACITY` | Workshop bays | `10` |
| `CFG_PHOTO_ARCHIVE_AFTER_DAYS` | Photo cold-storage threshold | `90` |
| `CFG_DOCUMENT_ARCHIVE_AFTER_DAYS` | Document archival threshold | `365` |
| `CFG_IMAGE_MAX_DIMENSION` | Image compression target | `1920` |
| `CFG_IMAGE_QUALITY` | JPEG/WebP quality | `85` |
| `CFG_MEDIA_SESSION_TTL_HOURS` | Upload session timeout | `24` |
| `CFG_OCR_ENGINE_VERSION` | PaddleOCR version | `PP-OCRv3` |
| `CFG_OCR_LANG` | OCR language | `fr` |
| `CFG_OCR_CONFIDENCE_THRESHOLD_DEFAULT` | OCR confidence | `0.75` |
| `CFG_INSPECTION_APPROVAL_EXPIRY_DAYS` | Approval link TTL | `7` |
| `CFG_NOTIFICATION_MAX_RETRIES` | Notification retry limit | `3` |
| `CFG_QUIET_HOURS_START` | Quiet hours start | `22:00` |
| `CFG_QUIET_HOURS_END` | Quiet hours end | `08:00` |
| `CFG_REMINDER_DELAY_1_DAYS` | First reminder | `7` |
| `CFG_REMINDER_DELAY_2_DAYS` | Second reminder | `14` |
| `CFG_REMINDER_DELAY_3_DAYS` | Third reminder | `30` |
| `CFG_CONFIG_CACHE_TTL_SECONDS` | Settings cache TTL | `60` |
| `CFG_SMS_PROVIDER` | SMS provider name | *(optional)* |
| `CFG_SMS_API_URL` | SMS API URL | *(optional)* |
| `CFG_SMS_API_KEY` | SMS API key | *(optional)* |
| `CFG_GTK3_DLL_DIR` | Windows GTK3 path (Windows dev only) | `C:\GTK3\bin` |

---

## 7. Database

### Engine & connection

| Item | Value |
|------|-------|
| Engine | PostgreSQL 15 |
| Driver | asyncpg 0.30.0 |
| ORM | SQLAlchemy 2.0.41 (async) |
| Migrations | Alembic 1.15.2 (47 versions) |
| Pool size | 10 (+ 20 overflow) |
| Host (dev) | `localhost:5433` (Docker) or `localhost:5432` (native) |
| Database name | `xpert_erp` |

### Migration commands

```bash
cd backend
alembic upgrade head          # Apply all pending migrations
alembic revision --autogenerate -m "description"  # Create new migration
alembic downgrade -1          # Rollback one version
```

Migrations run automatically via FastAPI lifespan on every container start.

### Key tables

| Table | Purpose |
|-------|---------|
| `app_user` | Users (auth) |
| `rbac_role` / `rbac_permission` | RBAC |
| `audit_log` | Full audit trail |
| `customer` | Customer CRM |
| `vehicle` | Vehicles |
| `repair_order` | RO workflow |
| `ro_labor_line` / `ro_part_line` | RO line items |
| `quotation` | Quotations |
| `invoice` | Customer invoices |
| `payment` | Payments |
| `advance_payment` | Deposits |
| `parts` | Parts catalog |
| `stock_movement` | Inventory tracking |
| `supplier` / `purchase_order` / `supplier_invoice` | Procurement |
| `cash_session` | Cash register |
| `credit_note` / `refund` | Credit & refunds |
| `bon_de_retour` | Return orders |
| `inspection` / `inspection_approval` | Inspections |
| `ro_media` | Photos/videos |
| `document` | Document archive |
| `notification_log` / `notification_template` | Notifications |
| `accounting_export` | Export records |
| `garage_setting` | Runtime CFG_* |
| `kpi_snapshot` | KPI cache |
| `ocr_extraction` | OCR results |

---

## 8. Backup & Disaster Recovery

### Daily logical backup

Script: `infra/scripts/backup.sh`

What it does:
1. `pg_dump` → custom format + gzip → upload to `s3://${BACKUP_S3_BUCKET}/dumps/`
2. MinIO bucket mirror (`xpert-documents`, `xpert-media`) → S3
3. Sync WAL archive → S3

```bash
# Run manually
docker compose -f infra/docker-compose.yml --profile backup run --rm backup

# Recommended cron (02:00 daily)
0 2 * * * cd /path/to/Xpert-ERP && docker compose -f infra/docker-compose.yml --profile backup run --rm backup >> /var/log/xpert_backup.log 2>&1
```

Retention: `BACKUP_RETENTION_DAYS` (default: 7 days).

### Weekly PITR base backup

Script: `infra/scripts/pitr_basebackup.sh`

```bash
# Recommended cron (03:00 every Sunday)
0 3 * * 0 cd /path/to/Xpert-ERP && docker compose -f infra/docker-compose.yml exec -T db bash /scripts/pitr_basebackup.sh >> /var/log/xpert_pitr.log 2>&1
```

### Restore from pg_dump

```bash
# List available dumps (printed by restore.sh)
docker compose -f infra/docker-compose.yml --profile backup run --rm backup bash /scripts/restore.sh

# Manual restore to a test instance
POSTGRES_HOST=localhost POSTGRES_PORT=5433 \
  bash infra/scripts/restore.sh xpert_erp_<TIMESTAMP>.dump
```

### Point-in-time recovery (PITR)

1. Stop PostgreSQL container
2. Download base backup from `s3://${BACKUP_S3_BUCKET}/pitr-base-backups/<DATE>/`
3. Extract into `pg_data` volume
4. Download WAL files from `s3://${BACKUP_S3_BUCKET}/wal-archive/` into `pg_wal_archive`
5. Create `recovery.signal` in data directory
6. Set `recovery_target_time` in `postgresql.conf`
7. Start PostgreSQL — WAL replay proceeds automatically

Full procedure: `docs/operations/runbook.md`

---

## 9. CI/CD

### GitHub Actions

File: `.github/workflows/ci.yml`

**Triggers:** push/PR to `develop`

#### Backend job

Services spun up:
- PostgreSQL 15 on `:5432` (DB: `xpert_test`)
- Redis 7 on `:6379`

Steps:
1. Setup Python 3.11
2. `pip install -e ".[dev]"`
3. Hard-coded values check: `.github/scripts/check_hardcoded.sh`
4. `ruff check` + `ruff format --check`
5. `mypy app`
6. `pytest` (≥50% coverage required)

#### Frontend job

Steps:
1. Setup Node 20
2. `npm ci`
3. `npx tsc --noEmit`
4. `npm run lint`
5. `npm run build`

---

## 10. Ports Reference

| Service | Host port | Container port | Notes |
|---------|-----------|----------------|-------|
| FastAPI API | **8000** | 8000 | `/api/v1/*` |
| Vite dev server | **5173** | 5173 | Dev only |
| PostgreSQL | **5433** | 5432 | Host uses 5433 to avoid conflicts |
| Redis | **6379** | 6379 | |
| MinIO API | **9000** | 9000 | S3-compatible |
| MinIO Console | **9001** | 9001 | Admin UI |
| Mailpit SMTP | **1025** | 1025 | Dev only |
| Mailpit Web UI | **8025** | 8025 | Dev only — view sent emails |

---

## 11. Production Deployment Checklist

### Secrets & configuration
- [ ] Generate a new `SECRET_KEY` (64 random bytes as hex)
- [ ] Set `ENVIRONMENT=production`, `DEBUG=false`
- [ ] Set `ALLOWED_ORIGINS` to the production domain(s)
- [ ] Set `FRONTEND_BASE_URL` to the production frontend URL
- [ ] Configure real SMTP credentials (`SMTP_HOST`, `SMTP_USERNAME`, etc.)
- [ ] Set all PDF branding variables (`PDF_GARAGE_NAME`, `PDF_GARAGE_ADDRESS`, etc.)
- [ ] Store secrets in a secret manager (AWS Secrets Manager, Vault, etc.) — not plain `.env`

### Database
- [ ] Use a managed PostgreSQL service (RDS, Supabase, etc.) or dedicated server with replication
- [ ] Change `DATABASE_URL` to point to production DB host
- [ ] Remove the `host.docker.internal` workaround — API should connect to DB via Docker network or managed service hostname
- [ ] Enable SSL on DB connection (`?ssl=require`)
- [ ] Run `alembic upgrade head` before first deploy (or let the lifespan hook do it)
- [ ] Schedule daily backups + weekly PITR base backups (`BACKUP_S3_*` vars)

### Redis
- [ ] Use managed Redis (ElastiCache, Upstash, etc.) or replicated cluster
- [ ] Set a strong `REDIS_PASSWORD`
- [ ] Enable TLS on Redis connection

### Object storage
- [ ] Use AWS S3 (or MinIO on dedicated infrastructure) — not the dev MinIO container
- [ ] Create buckets: `xpert-documents`, `xpert-media`, `xpert-backups`
- [ ] Set `S3_PUBLIC_ENDPOINT_URL` to the public-facing endpoint for presigned URLs
- [ ] Use a dedicated IAM user with minimal permissions for the app (`S3_ACCESS_KEY_ID` / `S3_SECRET_ACCESS_KEY`)
- [ ] Use a separate IAM user for backups (`BACKUP_S3_ACCESS_KEY` / `BACKUP_S3_SECRET_KEY`)

### Backend container
- [ ] Use the Gunicorn CMD from `Dockerfile.backend` (not `--reload`)
- [ ] Remove the `../backend:/app` bind-mount (use `COPY` from Dockerfile instead)
- [ ] Scale workers: `--workers N` (N = 2 × CPU cores + 1 is typical)
- [ ] Mount logs volume to host or ship logs to a log aggregator

### Frontend
- [ ] Set `VITE_API_BASE_URL` to the production API URL **before** running `npm run build`
- [ ] Serve `frontend/dist/` via Nginx (see reverse proxy note below)

### Reverse proxy (Nginx)
- [ ] Terminate TLS at Nginx
- [ ] Route `/api/*` → `http://api:8000` (proxy_pass)
- [ ] Serve `frontend/dist/` as static files for all other paths (SPA fallback)
- [ ] Configure gzip compression
- [ ] Set `proxy_read_timeout` high enough for PDF generation and OCR (recommend ≥60 s)

### Mailpit
- [ ] Remove or disable the `mailpit` service in production compose
- [ ] Configure a real SMTP relay

### Monitoring & observability
- [ ] Ship logs to an aggregator (ELK, Loki, CloudWatch, etc.)
- [ ] Set up error tracking (Sentry)
- [ ] Configure uptime monitoring on `/api/v1/health`
- [ ] Set up DB metrics (slow query log, connections)

### Security hardening
- [ ] Enable HTTPS only (HTTP → HTTPS redirect at Nginx)
- [ ] Set strict CORS (`ALLOWED_ORIGINS` = exact production domain)
- [ ] Rate limiting at Nginx or API Gateway level
- [ ] Consider WAF (Cloudflare, AWS WAF)
- [ ] Review and tighten `AUTH_MAX_FAILED_ATTEMPTS` and `AUTH_LOCKOUT_MINUTES`

---

## 12. Running the Full Stack Locally

```bash
# 1. Copy and fill in the env file
cp .env.example .env
# Edit .env with your values

# 2. Start infrastructure services
docker compose -f infra/docker-compose.yml up -d db redis minio mailpit

# 3. Wait for DB to be ready, then run migrations
cd backend
pip install -e ".[dev]"         # first time only
alembic upgrade head

# 4. Start the API (dev mode with reload)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --log-config uvicorn_log_config.json

# 5. In another terminal, start the frontend
cd frontend
npm install                     # first time only
npm run dev                     # http://localhost:5173

# 6. (Optional) Start the API via Docker instead of steps 4
docker compose -f infra/docker-compose.yml up -d api
```

**Useful URLs (dev):**
| URL | Purpose |
|-----|---------|
| http://localhost:5173 | Frontend |
| http://localhost:8000/api/v1/health | API health check |
| http://localhost:8000/docs | Swagger UI |
| http://localhost:9001 | MinIO console |
| http://localhost:8025 | Mailpit (view sent emails) |

---

*Generated 2026-06-27 from codebase scan. Keep this file up-to-date when infrastructure changes.*
