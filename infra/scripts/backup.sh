#!/usr/bin/env bash
# Daily backup: PostgreSQL logical dump + MinIO bucket mirror + WAL archive sync.
# Run via: docker compose --profile backup run --rm backup
# Or directly on a host with pg_dump and mc installed.
set -euo pipefail

BACKUP_DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_TMP="/tmp/xpert_backup_${BACKUP_DATE}"
S3_BACKUP_BUCKET="${BACKUP_S3_BUCKET:-xpert-backups}"
S3_BACKUP_ENDPOINT="${BACKUP_S3_ENDPOINT:-${S3_ENDPOINT_URL}}"
BACKUP_S3_ACCESS="${BACKUP_S3_ACCESS_KEY:-${S3_ACCESS_KEY_ID}}"
BACKUP_S3_SECRET="${BACKUP_S3_SECRET_KEY:-${S3_SECRET_ACCESS_KEY}}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-7}"
PG_HOST="${POSTGRES_HOST:-db}"

log() { echo "[$(date -Iseconds)] $*"; }

mkdir -p "${BACKUP_TMP}"
trap 'rm -rf "${BACKUP_TMP}"' EXIT

log "=== Xpert-ERP backup ${BACKUP_DATE} started ==="

# ---------------------------------------------------------------------------
# 1. PostgreSQL logical dump (custom format, compressed)
# ---------------------------------------------------------------------------
log "Dumping PostgreSQL database '${POSTGRES_DB:-xpert_erp}'..."
PGPASSWORD="${POSTGRES_PASSWORD}" pg_dump \
  -h "${PG_HOST}" \
  -p "${POSTGRES_PORT:-5432}" \
  -U "${POSTGRES_USER:-xpert}" \
  -d "${POSTGRES_DB:-xpert_erp}" \
  --format=custom \
  --compress=9 \
  --file="${BACKUP_TMP}/xpert_erp_${BACKUP_DATE}.dump"
log "Dump complete: $(du -sh "${BACKUP_TMP}/xpert_erp_${BACKUP_DATE}.dump" | cut -f1)"

# ---------------------------------------------------------------------------
# 2. Configure MinIO client alias for backup target
# ---------------------------------------------------------------------------
mc alias set backup_target "${S3_BACKUP_ENDPOINT}" "${BACKUP_S3_ACCESS}" "${BACKUP_S3_SECRET}" --quiet

# ---------------------------------------------------------------------------
# 3. Upload pg_dump to backup bucket
# ---------------------------------------------------------------------------
log "Uploading dump to s3://${S3_BACKUP_BUCKET}/pg-dumps/..."
mc cp \
  "${BACKUP_TMP}/xpert_erp_${BACKUP_DATE}.dump" \
  "backup_target/${S3_BACKUP_BUCKET}/pg-dumps/xpert_erp_${BACKUP_DATE}.dump"
log "Dump uploaded."

# ---------------------------------------------------------------------------
# 4. Mirror MinIO application buckets to backup bucket
# ---------------------------------------------------------------------------
log "Mirroring application buckets to backup target..."
mc alias set local_minio "${S3_ENDPOINT_URL}" "${S3_ACCESS_KEY_ID}" "${S3_SECRET_ACCESS_KEY}" --quiet

mc mirror \
  "local_minio/${S3_BUCKET_DOCUMENTS}" \
  "backup_target/${S3_BACKUP_BUCKET}/minio-mirror/documents/" \
  --overwrite --quiet
log "Documents bucket mirrored."

mc mirror \
  "local_minio/${S3_BUCKET_MEDIA}" \
  "backup_target/${S3_BACKUP_BUCKET}/minio-mirror/media/" \
  --overwrite --quiet
log "Media bucket mirrored."

# ---------------------------------------------------------------------------
# 5. Sync WAL archive to backup bucket (enables PITR)
# ---------------------------------------------------------------------------
WAL_ARCHIVE_DIR="/var/lib/postgresql/wal_archive"
if [ -d "${WAL_ARCHIVE_DIR}" ] && [ "$(ls -A "${WAL_ARCHIVE_DIR}" 2>/dev/null)" ]; then
  log "Syncing WAL archive to backup bucket..."
  mc mirror \
    "${WAL_ARCHIVE_DIR}/" \
    "backup_target/${S3_BACKUP_BUCKET}/wal-archive/" \
    --overwrite --quiet
  log "WAL archive synced."
else
  log "WAL archive directory empty or not mounted — skipping WAL sync."
fi

# ---------------------------------------------------------------------------
# 6. Prune pg_dumps older than RETENTION_DAYS
# ---------------------------------------------------------------------------
log "Pruning pg-dumps older than ${RETENTION_DAYS} days..."
mc rm \
  --recursive --force \
  --older-than "${RETENTION_DAYS}d" \
  "backup_target/${S3_BACKUP_BUCKET}/pg-dumps/" 2>/dev/null || true
log "Pruning complete."

log "=== Backup ${BACKUP_DATE} finished successfully ==="
