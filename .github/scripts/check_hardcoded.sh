#!/usr/bin/env bash
# check_hardcoded.sh
#
# Enforce the no-hard-coded-values rule:
#   Business thresholds, timeouts, limits, and rates must come from
#   config.py (pydantic-settings) or the garage_setting DB table.
#   They must NOT appear as bare literals in module service/router files.
#
# Exit 0 = clean.  Exit 1 = violations found.
#
# Exempted paths:
#   backend/app/core/config.py        — the canonical source of defaults
#   backend/migrations/               — SQL defaults are acceptable here
#   backend/app/*/tests/              — test files may use literal values
#   backend/tests/                    — same
#   Any file matching *_seed.py       — seed scripts may use literal strings

set -euo pipefail

BACKEND="backend/app/modules"
VIOLATIONS=0

# ---------------------------------------------------------------------------
# 1. Detect bare integer literals assigned to known threshold variable names
#    outside of config.py.
#
#    Pattern:  <name> = <digits>   (with optional type annotation)
#    where <name> matches a known CFG_* key.
# ---------------------------------------------------------------------------

THRESHOLD_NAMES=(
  "expire_minutes"
  "expire_days"
  "max_failed_attempts"
  "lockout_minutes"
  "max_retries"
  "cache_ttl"
  "ttl_seconds"
  "ttl_hours"
  "archive_after_days"
  "max_dimension"
  "chunk_size_bytes"
  "upload_size_bytes"
  "refresh_interval"
  "workshop_capacity"
  "reminder_delay"
  "approval_expiry"
  "match_tolerance"
  "quiet_hours"
  "signed_url_expiry"
  "pool_size"
  "max_overflow"
  "backup_count"
)

EXCLUDE_PATTERN="(test_|_test\.py|_seed\.py|conftest\.py)"

echo "Checking for hard-coded threshold literals in ${BACKEND}..."

for name in "${THRESHOLD_NAMES[@]}"; do
  # Find assignments like: some_name = 30  or  name: int = 300
  matches=$(grep -rn --include="*.py" \
    -E "${name}\s*[:=]+\s*[0-9]+" \
    "${BACKEND}" \
    | grep -Ev "${EXCLUDE_PATTERN}" \
    || true)

  if [[ -n "$matches" ]]; then
    echo ""
    echo "ERROR: Hard-coded value for '${name}' found — use settings or SettingsService:"
    echo "$matches"
    VIOLATIONS=$((VIOLATIONS + 1))
  fi
done

# ---------------------------------------------------------------------------
# 2. Detect hard-coded S3 bucket names or Redis key prefixes as string
#    literals in module files (must come from settings).
# ---------------------------------------------------------------------------

echo "Checking for hard-coded S3 bucket / Redis key literals..."

LITERAL_PATTERNS=(
  "\"xpert-"         # hard-coded S3 bucket names like "xpert-media"
  "'xpert-"
)

for pat in "${LITERAL_PATTERNS[@]}"; do
  matches=$(grep -rn --include="*.py" \
    -F "$pat" \
    "${BACKEND}" \
    | grep -Ev "${EXCLUDE_PATTERN}" \
    || true)

  if [[ -n "$matches" ]]; then
    echo ""
    echo "ERROR: Hard-coded literal '${pat}' found — use settings.*:"
    echo "$matches"
    VIOLATIONS=$((VIOLATIONS + 1))
  fi
done

# ---------------------------------------------------------------------------
# 3. Detect hard-coded JWT algorithm strings outside config.py
# ---------------------------------------------------------------------------

echo "Checking for hard-coded JWT algorithm strings..."

matches=$(grep -rn --include="*.py" \
  -E '"(HS256|RS256|HS512|RS512)"' \
  "${BACKEND}" \
  | grep -Ev "${EXCLUDE_PATTERN}" \
  || true)

if [[ -n "$matches" ]]; then
  echo ""
  echo "ERROR: Hard-coded JWT algorithm string found — use settings.algorithm:"
  echo "$matches"
  VIOLATIONS=$((VIOLATIONS + 1))
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

echo ""
if [[ $VIOLATIONS -eq 0 ]]; then
  echo "check_hardcoded: PASSED (0 violations)"
  exit 0
else
  echo "check_hardcoded: FAILED (${VIOLATIONS} violation(s))"
  exit 1
fi
