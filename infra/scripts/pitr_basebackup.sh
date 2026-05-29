#!/usr/bin/env bash
# Take a PostgreSQL base backup using pg_basebackup.
# Run weekly (e.g. every Sunday) alongside the daily WAL archive sync.
# A base backup + archived WAL files enable point-in-time recovery (PITR)
# to any second within the 7-day retention window.
#
# Usage: pitr_basebackup.sh
set -euo pipefail

BACKUP_DATE=$(date +%Y%m%d_%H%M%S)
BASEBACKUP_TMP="/tmp/xpert_basebackup_${BACKUP_DATE}"
S3_BACKUP_BUCKET="${BACKUP_S3_BUCKET:-xpert-backups}"
S3_BACKUP_ENDPOINT="${BACKUP_S3_ENDPOINT:-${S3_ENDPOINT_URL}}"
BACKUP_S3_ACCESS="${BACKUP_S3_ACCESS_KEY:-${S3_ACCESS_KEY_ID}}"
BACKUP_S3_SECRET="${BACKUP_S3_SECRET_KEY:-${S3_SECRET_ACCESS_KEY}}"
PG_HOST="${POSTGRES_HOST:-db}"
RETENTION_WEEKS=2

log() { echo "[$(date -Iseconds)] $*"; }

mkdir -p "${BASEBACKUP_TMP}"
trap 'rm -rf "${BASEBACKUP_TMP}"' EXIT

log "=== PITR base backup ${BACKUP_DATE} started ==="

# ---------------------------------------------------------------------------
# Take base backup
# ---------------------------------------------------------------------------
log "Running pg_basebackup against ${PG_HOST}..."
PGPASSWORD="${POSTGRES_PASSWORD}" pg_basebackup \
  -h "${PG_HOST}" \
  -p "${POSTGRES_PORT:-5432}" \
  -U "${POSTGRES_USER:-xpert}" \
  -D "${BASEBACKUP_TMP}/base" \
  --format=tar \
  --gzip \
  --compress=9 \
  --checkpoint=fast \
  --wal-method=stream \
  --progress
log "Base backup complete."

# ---------------------------------------------------------------------------
# Upload base backup to S3
# ---------------------------------------------------------------------------
mc alias set backup_target "${S3_BACKUP_ENDPOINT}" "${BACKUP_S3_ACCESS}" "${BACKUP_S3_SECRET}" --quiet

log "Uploading base backup to s3://${S3_BACKUP_BUCKET}/pitr-base-backups/${BACKUP_DATE}/..."
mc mirror \
  "${BASEBACKUP_TMP}/base/" \
  "backup_target/${S3_BACKUP_BUCKET}/pitr-base-backups/${BACKUP_DATE}/" \
  --overwrite --quiet
log "Base backup uploaded."

# ---------------------------------------------------------------------------
# Prune base backups older than RETENTION_WEEKS weeks
# ---------------------------------------------------------------------------
log "Pruning base backups older than ${RETENTION_WEEKS} weeks..."
mc rm \
  --recursive --force \
  --older-than "$((RETENTION_WEEKS * 7))d" \
  "backup_target/${S3_BACKUP_BUCKET}/pitr-base-backups/" 2>/dev/null || true
log "Pruning complete."

log "=== PITR base backup ${BACKUP_DATE} finished ==="
log ""
log "To perform a PITR restore:"
log "  1. Stop the PostgreSQL container."
log "  2. Download a base backup from s3://${S3_BACKUP_BUCKET}/pitr-base-backups/<DATE>/"
log "     and extract it into the pg_data volume."
log "  3. Download WAL files from s3://${S3_BACKUP_BUCKET}/wal-archive/ into the"
log "     pg_wal_archive volume."
log "  4. Create a recovery.signal file in the data directory."
log "  5. Set recovery_target_time in postgresql.conf."
log "  6. Start PostgreSQL — it will replay WAL to the target time."
log "  See docs/operations/runbook.md for the full PITR procedure."
