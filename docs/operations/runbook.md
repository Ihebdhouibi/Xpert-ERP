# Xpert-ERP Operator Runbook

This document covers everything an operator needs to manage a running Xpert-ERP instance with no prior project knowledge.

---

## Prerequisites

| Tool | Minimum version | Purpose |
|---|---|---|
| Docker | 24+ | Runs all services |
| Docker Compose | 2.20+ | Service orchestration |
| Git | 2.x | Cloning the repository |
| MinIO Client (`mc`) | Latest | Backup / restore operations |
| `psql` / `pg_restore` | 15 | DB access / restore (available inside the `db` container) |

---

## Directory Layout

```
infra/
  docker-compose.yml        Main service definitions
  Dockerfile.backup         Image for backup service (postgres + mc)
  scripts/
    backup.sh               Daily backup script
    restore.sh              Restore from pg_dump
    pitr_basebackup.sh      Weekly PITR base backup
docs/
  operations/
    runbook.md              This file
    backup_restore_drill_*.md  Drill records
backend/                    FastAPI application
frontend/                   React application
logs/                       Rotating log files (mounted from host)
```

---

## Environment Variables

Copy `.env.example` to `.env` at the project root and fill in every value before starting.

| Variable | Description |
|---|---|
| `POSTGRES_USER` | PostgreSQL username |
| `POSTGRES_PASSWORD` | PostgreSQL password |
| `POSTGRES_DB` | Database name |
| `DATABASE_URL` | Full async DB URL for the API |
| `REDIS_PASSWORD` | Redis password |
| `REDIS_URL` | Full Redis URL for the API |
| `MINIO_ROOT_USER` | MinIO admin username |
| `MINIO_ROOT_PASSWORD` | MinIO admin password |
| `S3_ENDPOINT_URL` | MinIO/S3 endpoint (e.g. `http://localhost:9000`) |
| `S3_ACCESS_KEY_ID` | S3 access key for the application |
| `S3_SECRET_ACCESS_KEY` | S3 secret key for the application |
| `S3_BUCKET_DOCUMENTS` | Bucket name for uploaded documents |
| `S3_BUCKET_MEDIA` | Bucket name for photos/videos |
| `SECRET_KEY` | 64-byte hex secret for JWT signing |
| `BACKUP_S3_BUCKET` | Bucket for backup storage |
| `BACKUP_S3_ENDPOINT` | Backup target S3 endpoint |
| `BACKUP_S3_ACCESS_KEY` | Dedicated backup IAM key |
| `BACKUP_S3_SECRET_KEY` | Dedicated backup IAM secret |
| `BACKUP_RETENTION_DAYS` | Days to retain pg_dump files (default: 7) |
| `POSTGRES_HOST` | Hostname of PostgreSQL (for backup scripts; default: `db`) |
| `LOG_LEVEL` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |

Generate `SECRET_KEY`:
```bash
python -c "import secrets; print(secrets.token_hex(64))"
```

---

## Startup

### Full stack (first time or after a clean reset)

```bash
# 1. Clone and configure
git clone <repo_url> && cd Xpert-ERP
cp .env.example .env
# Edit .env with real values

# 2. Start infrastructure services
docker compose -f infra/docker-compose.yml up -d db redis minio

# 3. Wait for DB to be healthy, then run migrations
docker compose -f infra/docker-compose.yml exec db pg_isready -U xpert
cd backend && alembic upgrade head

# 4. Seed initial admin user (first run only)
python backend/seed_admin.py

# 5. Start the API
docker compose -f infra/docker-compose.yml up -d api

# 6. Start the frontend (dev mode)
cd frontend && npm install && npm run dev
```

### Normal restart (services already configured)

```bash
docker compose -f infra/docker-compose.yml up -d
```

Check all services are healthy:
```bash
docker compose -f infra/docker-compose.yml ps
```

---

## Shutdown

### Graceful stop (data preserved)

```bash
docker compose -f infra/docker-compose.yml stop
```

### Full teardown (volumes preserved)

```bash
docker compose -f infra/docker-compose.yml down
```

### Full teardown including volumes (DESTRUCTIVE — destroys all data)

```bash
docker compose -f infra/docker-compose.yml down -v
```

---

## Backup

### Daily backup (pg_dump + MinIO mirror + WAL sync)

Run manually:
```bash
docker compose -f infra/docker-compose.yml --profile backup run --rm backup
```

Schedule via host cron (recommended: 02:00 daily):
```cron
0 2 * * * cd /path/to/Xpert-ERP && docker compose -f infra/docker-compose.yml --profile backup run --rm backup >> /var/log/xpert_backup.log 2>&1
```

### Weekly PITR base backup

Run manually:
```bash
docker compose -f infra/docker-compose.yml exec backup bash /scripts/pitr_basebackup.sh
```

Schedule via host cron (recommended: 03:00 every Sunday):
```cron
0 3 * * 0 cd /path/to/Xpert-ERP && docker compose -f infra/docker-compose.yml exec -T db bash /scripts/pitr_basebackup.sh >> /var/log/xpert_pitr.log 2>&1
```

### List available backups

```bash
docker compose -f infra/docker-compose.yml --profile backup run --rm backup bash /scripts/restore.sh
```

---

## Restore

### Restore from pg_dump (logical restore — recommended for most cases)

```bash
# 1. Spin up a clean restore target (do NOT run against production)
docker run -d \
  --name xpert_restore_target \
  -e POSTGRES_USER=xpert \
  -e POSTGRES_PASSWORD=<password> \
  -e POSTGRES_DB=xpert_erp \
  -p 5433:5432 \
  postgres:15-alpine

# 2. List available dumps
POSTGRES_HOST=localhost bash infra/scripts/restore.sh

# 3. Restore chosen dump
POSTGRES_HOST=localhost POSTGRES_PORT=5433 \
  bash infra/scripts/restore.sh xpert_erp_<TIMESTAMP>.dump

# 4. Verify integrity (row count checks print automatically)

# 5. Promote restore target to production by updating DATABASE_URL and restarting the API
```

### Point-in-time recovery (PITR)

Use PITR when you need to recover to a specific second (e.g. accidental data deletion).

```bash
# 1. Stop the API to prevent new writes
docker compose -f infra/docker-compose.yml stop api

# 2. Stop the database
docker compose -f infra/docker-compose.yml stop db

# 3. Download the nearest base backup taken BEFORE the target time
mc cp -r "backup_target/xpert-backups/pitr-base-backups/<BASE_DATE>/" /tmp/pitr_restore/

# 4. Replace pg_data volume contents with the base backup
docker run --rm \
  -v xpert-erp_pg_data:/var/lib/postgresql/data \
  -v /tmp/pitr_restore:/backup \
  postgres:15-alpine \
  bash -c "rm -rf /var/lib/postgresql/data/* && tar -xzf /backup/base.tar.gz -C /var/lib/postgresql/data/"

# 5. Download WAL archive into pg_wal_archive volume
mc mirror \
  "backup_target/xpert-backups/wal-archive/" \
  /tmp/wal_archive/
docker run --rm \
  -v xpert-erp_pg_wal_archive:/wal_archive \
  -v /tmp/wal_archive:/src \
  alpine sh -c "cp -r /src/. /wal_archive/"

# 6. Add recovery configuration
# Create recovery.signal and set recovery_target_time in postgresql.conf
# inside the pg_data volume (edit via a temporary container):
docker run --rm \
  -v xpert-erp_pg_data:/var/lib/postgresql/data \
  postgres:15-alpine \
  bash -c "
    touch /var/lib/postgresql/data/recovery.signal
    echo \"restore_command = 'cp /var/lib/postgresql/wal_archive/%f %p'\" >> /var/lib/postgresql/data/postgresql.conf
    echo \"recovery_target_time = '2026-05-29 11:45:00'\" >> /var/lib/postgresql/data/postgresql.conf
    echo \"recovery_target_action = 'promote'\" >> /var/lib/postgresql/data/postgresql.conf
  "

# 7. Start PostgreSQL — it will replay WAL and stop at the target time
docker compose -f infra/docker-compose.yml start db

# 8. Watch logs to confirm recovery completes
docker compose -f infra/docker-compose.yml logs -f db

# 9. Once promoted, remove recovery settings and restart the API
docker compose -f infra/docker-compose.yml start api
```

---

## Log Rotation

Logs are written to the `logs/` directory (mounted into the API container at `/app/logs`).

Default rotation settings (configurable via `.env`):
- `LOG_MAX_BYTES=10485760` (10 MB per file)
- `LOG_BACKUP_COUNT=5` (5 rotated files kept)

Python's `RotatingFileHandler` handles rotation automatically. No external logrotate config required.

To view live API logs:
```bash
docker compose -f infra/docker-compose.yml logs -f api
```

To view a specific component log:
```bash
tail -f logs/auth.log
tail -f logs/invoice.log
tail -f logs/db.log
```

---

## Database Migrations

Apply pending migrations:
```bash
cd backend && alembic upgrade head
```

Check current revision:
```bash
cd backend && alembic current
```

Roll back one revision:
```bash
cd backend && alembic downgrade -1
```

Generate a new migration after model changes:
```bash
cd backend && alembic revision --autogenerate -m "describe the change"
```

---

## Alert Response

### API returns 500 errors

1. Check API logs: `docker compose -f infra/docker-compose.yml logs --tail=100 api`
2. Check DB connectivity: `docker compose -f infra/docker-compose.yml exec db pg_isready -U xpert`
3. Check Redis: `docker compose -f infra/docker-compose.yml exec redis redis-cli -a $REDIS_PASSWORD ping`
4. Restart the API if the issue is transient: `docker compose -f infra/docker-compose.yml restart api`

### Database connection pool exhausted

Symptom: `asyncpg.TooManyConnectionsError` in logs.

1. Increase `DATABASE_POOL_SIZE` and `DATABASE_MAX_OVERFLOW` in `.env`.
2. Restart the API: `docker compose -f infra/docker-compose.yml restart api`
3. If persistent, check for long-running queries: `SELECT * FROM pg_stat_activity WHERE state = 'active' ORDER BY duration DESC;`

### Disk space low

1. Check disk usage: `docker system df`
2. Prune unused images/containers: `docker system prune -f`
3. Check log sizes: `du -sh logs/*`
4. Check MinIO volume: `docker compose -f infra/docker-compose.yml exec minio du -sh /data`
5. If WAL archive is growing large, verify the backup sync job is running and pruning old files.

### Backup job failing

1. Check cron logs: `tail -50 /var/log/xpert_backup.log`
2. Verify backup target credentials: `mc alias ls backup_target`
3. Run backup manually to see full error output:
   ```bash
   docker compose -f infra/docker-compose.yml --profile backup run --rm backup
   ```

### Redis unreachable

1. Check Redis container: `docker compose -f infra/docker-compose.yml ps redis`
2. Restart: `docker compose -f infra/docker-compose.yml restart redis`
3. If Redis data is lost (expected on restart with no persistence), the API will rebuild its cache on demand within `CFG_CONFIG_CACHE_TTL_SECONDS`.

### MinIO unreachable

1. Check MinIO container: `docker compose -f infra/docker-compose.yml ps minio`
2. Restart: `docker compose -f infra/docker-compose.yml restart minio`
3. Document uploads and signed URL generation will fail until MinIO is healthy. The API returns 503 for document endpoints during this window.

---

## Useful One-liners

```bash
# Check all service health
docker compose -f infra/docker-compose.yml ps

# Open a psql shell
docker compose -f infra/docker-compose.yml exec db psql -U xpert xpert_erp

# Open a Redis CLI shell
docker compose -f infra/docker-compose.yml exec redis redis-cli -a $REDIS_PASSWORD

# Tail all service logs
docker compose -f infra/docker-compose.yml logs -f

# Check API health endpoint
curl http://localhost:8000/api/v1/health
```
