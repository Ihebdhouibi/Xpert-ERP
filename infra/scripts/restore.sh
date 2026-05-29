#!/usr/bin/env bash
# Restore PostgreSQL from a pg_dump backup stored in S3.
# Usage:
#   restore.sh                          — lists available dumps, then exits
#   restore.sh <DUMP_FILENAME>          — restores the named dump
#   restore.sh latest                   — restores the most recent dump
#
# WARNING: this script DROPS and recreates the target database.
# Only run on a dedicated restore environment, never against production.
set -euo pipefail

S3_BACKUP_BUCKET="${BACKUP_S3_BUCKET:-xpert-backups}"
S3_BACKUP_ENDPOINT="${BACKUP_S3_ENDPOINT:-${S3_ENDPOINT_URL}}"
BACKUP_S3_ACCESS="${BACKUP_S3_ACCESS_KEY:-${S3_ACCESS_KEY_ID}}"
BACKUP_S3_SECRET="${BACKUP_S3_SECRET_KEY:-${S3_SECRET_ACCESS_KEY}}"
PG_HOST="${POSTGRES_HOST:-db}"
PG_USER="${POSTGRES_USER:-xpert}"
PG_DB="${POSTGRES_DB:-xpert_erp}"
RESTORE_TMP="/tmp/xpert_restore"

log() { echo "[$(date -Iseconds)] $*"; }

mc alias set backup_target "${S3_BACKUP_ENDPOINT}" "${BACKUP_S3_ACCESS}" "${BACKUP_S3_SECRET}" --quiet

# ---------------------------------------------------------------------------
# List mode: no argument — print available dumps and exit
# ---------------------------------------------------------------------------
if [ $# -eq 0 ]; then
  log "Available dumps in s3://${S3_BACKUP_BUCKET}/pg-dumps/:"
  mc ls "backup_target/${S3_BACKUP_BUCKET}/pg-dumps/" | sort
  echo ""
  echo "Usage: $0 <DUMP_FILENAME>  OR  $0 latest"
  exit 0
fi

DUMP_ARG="$1"

# ---------------------------------------------------------------------------
# Resolve dump filename
# ---------------------------------------------------------------------------
if [ "${DUMP_ARG}" = "latest" ]; then
  DUMP_FILE=$(mc ls "backup_target/${S3_BACKUP_BUCKET}/pg-dumps/" \
    | awk '{print $NF}' | sort | tail -1)
  if [ -z "${DUMP_FILE}" ]; then
    echo "ERROR: No dumps found in s3://${S3_BACKUP_BUCKET}/pg-dumps/"
    exit 1
  fi
  log "Latest dump resolved to: ${DUMP_FILE}"
else
  DUMP_FILE="${DUMP_ARG}"
fi

# ---------------------------------------------------------------------------
# Safety confirmation
# ---------------------------------------------------------------------------
echo ""
echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
echo "  WARNING: This will DROP and recreate database '${PG_DB}'"
echo "  on host '${PG_HOST}'."
echo "  Dump to restore: ${DUMP_FILE}"
echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
echo ""
read -r -p "Type 'yes' to confirm: " CONFIRM
if [ "${CONFIRM}" != "yes" ]; then
  echo "Aborted."
  exit 1
fi

mkdir -p "${RESTORE_TMP}"
trap 'rm -rf "${RESTORE_TMP}"' EXIT

# ---------------------------------------------------------------------------
# Download dump
# ---------------------------------------------------------------------------
log "Downloading ${DUMP_FILE}..."
mc cp \
  "backup_target/${S3_BACKUP_BUCKET}/pg-dumps/${DUMP_FILE}" \
  "${RESTORE_TMP}/${DUMP_FILE}"
log "Download complete: $(du -sh "${RESTORE_TMP}/${DUMP_FILE}" | cut -f1)"

# ---------------------------------------------------------------------------
# Drop and recreate target database
# ---------------------------------------------------------------------------
log "Dropping and recreating database '${PG_DB}'..."
PGPASSWORD="${POSTGRES_PASSWORD}" psql \
  -h "${PG_HOST}" -U "${PG_USER}" -d postgres \
  -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '${PG_DB}' AND pid <> pg_backend_pid();" \
  -c "DROP DATABASE IF EXISTS ${PG_DB};" \
  -c "CREATE DATABASE ${PG_DB} OWNER ${PG_USER};"

# ---------------------------------------------------------------------------
# Restore dump
# ---------------------------------------------------------------------------
log "Restoring dump..."
PGPASSWORD="${POSTGRES_PASSWORD}" pg_restore \
  -h "${PG_HOST}" \
  -U "${PG_USER}" \
  -d "${PG_DB}" \
  --no-owner \
  --role="${PG_USER}" \
  --exit-on-error \
  "${RESTORE_TMP}/${DUMP_FILE}"

# ---------------------------------------------------------------------------
# Integrity checks
# ---------------------------------------------------------------------------
log "Running integrity checks..."
PGPASSWORD="${POSTGRES_PASSWORD}" psql \
  -h "${PG_HOST}" -U "${PG_USER}" -d "${PG_DB}" \
  -c "\dt" \
  -c "SELECT count(*) AS app_users    FROM app_user;" \
  -c "SELECT count(*) AS customers    FROM customer;" \
  -c "SELECT count(*) AS vehicles     FROM vehicle;" \
  -c "SELECT count(*) AS repair_orders FROM repair_order;" \
  -c "SELECT count(*) AS invoices     FROM invoice;" \
  -c "SELECT count(*) AS audit_entries FROM audit_log;"

log "=== Restore of '${DUMP_FILE}' completed. Review row counts above. ==="
