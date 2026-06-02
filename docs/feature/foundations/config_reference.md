# CFG_* Configuration Reference

Complete catalog of all runtime-tunable settings for Xpert-ERP.

Settings are split into two tiers:

| Tier | How to set | Restartable? |
|------|-----------|-------------|
| **Infrastructure** | Environment variable / `.env` file | Requires restart |
| **Runtime (CFG_*)** | `garage_setting` DB table via `PUT /api/v1/settings/{key}` | Takes effect within `CFG_CONFIG_CACHE_TTL_SECONDS` |

Infrastructure settings (DB, Redis, S3, JWT secret) can only be set via
environment variables because they are needed before any database connection
is available.  All `CFG_*` prefixed settings are runtime-tunable through the
database settings table and are cached in Redis.

---

## Infrastructure Settings (env-only)

These are read once at startup from environment variables.  They cannot be
overridden at runtime.

| Key | Type | Required | Description |
|-----|------|----------|-------------|
| `DATABASE_URL` | string | yes | PostgreSQL async DSN (`postgresql+asyncpg://...`) |
| `REDIS_URL` | string | yes | Redis connection URL (`redis://host:port/db`) |
| `S3_ENDPOINT_URL` | string | yes | S3-compatible endpoint (MinIO in dev, AWS S3 in prod) |
| `S3_ACCESS_KEY_ID` | string | yes | S3 access key |
| `S3_SECRET_ACCESS_KEY` | string | yes | S3 secret key |
| `S3_BUCKET_DOCUMENTS` | string | yes | Bucket for PDF documents and GED files |
| `S3_BUCKET_MEDIA` | string | yes | Bucket for inspection photos/videos |
| `S3_REGION` | string | no | S3 region (default: `us-east-1`) |
| `SECRET_KEY` | string | yes | JWT signing key (RS256 or HS256) |
| `ALGORITHM` | string | no | JWT algorithm (default: `HS256`) |
| `ENVIRONMENT` | string | no | `development`, `staging`, or `production` (default: `development`) |
| `DEBUG` | bool | no | Enable SQLAlchemy echo and verbose logs (default: `false`) |
| `ALLOWED_ORIGINS` | list[string] | no | CORS allowed origins (default: `["http://localhost:5173"]`) |
| `LOG_LEVEL` | string | no | structlog level (default: `INFO`) |
| `LOG_DIR` | string | no | Directory for per-component log files (default: `logs`) |
| `SMTP_HOST` | string | no | SMTP server hostname |
| `SMTP_PORT` | int | no | SMTP port (default: `587`) |
| `SMTP_USERNAME` | string | no | SMTP username |
| `SMTP_PASSWORD` | string | no | SMTP password |
| `SMTP_USE_TLS` | bool | no | Enable STARTTLS (default: `true`) |
| `SMTP_FROM_ADDRESS` | string | no | Sender email address |
| `SMTP_FROM_NAME` | string | no | Sender display name (default: `Xpert-ERP`) |

---

## Runtime Settings (CFG_* — DB-backed)

These values live in the `garage_setting` table and are served through
`SettingsService.get_setting()` with a Redis cache layer.

Changing a value via `PUT /api/v1/settings/{key}?garage_id=0` takes effect
within `CFG_CONFIG_CACHE_TTL_SECONDS` seconds (default: 60 s) without
restarting the server.

`garage_id = 0` means a global default.  A non-zero `garage_id` creates a
per-garage override that takes precedence over the global default.

### Runtime settings cache

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `cfg_config_cache_ttl_seconds` | int | `60` | How long DB-backed CFG_* values are cached in Redis (seconds) |

### Security / Auth

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `access_token_expire_minutes` | int | `30` | Access JWT lifetime in minutes |
| `refresh_token_expire_days` | int | `7` | Refresh JWT lifetime in days |
| `auth_max_failed_attempts` | int | `5` | Failed login attempts before account lockout |
| `auth_lockout_minutes` | int | `15` | Duration of lockout window (minutes) |
| `password_reset_expiry_minutes` | int | `30` | Password-reset link validity (minutes) |
| `password_min_length` | int | `12` | Minimum password length (ASVS 2.1.1) |

### Document upload

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `max_upload_size_bytes` | int | `10485760` | Maximum document upload size (bytes, default 10 MB) |
| `signed_url_expiry_seconds` | int | `3600` | Pre-signed S3 URL validity (seconds, default 1 h) |

### PDF / Invoice appearance

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `pdf_garage_name` | string | `Xpert Garage` | Garage display name on PDFs |
| `pdf_garage_address` | string | `` | Garage address on PDFs |
| `pdf_garage_phone` | string | `` | Garage phone on PDFs |
| `pdf_garage_email` | string | `` | Garage email on PDFs |
| `pdf_garage_logo_path` | string | `` | Absolute path to logo file; empty = no logo |
| `pdf_vat_number` | string | `` | VAT registration number |
| `pdf_legal_mention` | string | `` | Legal mentions block |
| `pdf_bank_details` | string | `` | Bank details for payments |
| `pdf_footer_text` | string | `` | Custom footer text |
| `pdf_currency_symbol` | string | `€` | Currency symbol |
| `pdf_payment_terms` | string | `Paiement à 30 jours` | Default payment terms text |

### Cash register

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `cash_diff_require_reason` | bool | `true` | Require a reason when closing a session with a non-zero difference |

### Credit limits

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `credit_limit_mode` | string | `block` | `block` = reject issuance; `warn` = log only |
| `credit_currency` | string | `EUR` | ISO-4217 currency used for balance events |

### Parts / stock

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `cfg_allow_negative_stock` | bool | `false` | Allow on-hand quantity to go negative with an explicit reason |

### Purchase orders

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `cfg_po_match_tolerance_percent` | float | `5.0` | Price tolerance (%) for three-way match before flagging a mismatch |

### Media upload

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `cfg_upload_chunk_size_bytes` | int | `5242880` | S3 multipart minimum part size (bytes, default 5 MB) |
| `cfg_photo_archive_after_days` | int | `90` | Days after upload before a photo is moved to cold storage |
| `cfg_image_max_dimension` | int | `1920` | Client-side compression target — longest edge in pixels |
| `cfg_image_quality` | int | `85` | Client-side JPEG/WebP compression quality (0–100) |
| `cfg_media_session_ttl_hours` | int | `24` | Hours before an incomplete upload session expires |
| `s3_bucket_media_archive` | string | `` | Bucket for archived cold-storage media; falls back to `S3_BUCKET_MEDIA` |

### Inspections

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `cfg_inspection_approval_expiry_days` | int | `7` | Days a customer approval JWT link stays valid |

### KPI dashboard

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `cfg_kpi_refresh_interval_seconds` | int | `300` | Live KPI endpoint Redis cache TTL (seconds) |
| `cfg_kpi_workshop_capacity` | int | `10` | Number of workshop bays for occupancy KPI calculation |

### Accounting export

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `cfg_accounting_format` | string | `generic_csv` | Export format: `sage`, `cegid`, `ebp`, or `generic_csv` |

### Notifications

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `cfg_notification_max_retries` | int | `3` | Maximum delivery retry attempts before marking as failed |
| `cfg_quiet_hours_start` | string | `22:00` | HH:MM start of quiet window (no notifications sent) |
| `cfg_quiet_hours_end` | string | `08:00` | HH:MM end of quiet window (may cross midnight) |
| `cfg_reminder_delay_1_days` | int | `7` | Days after due date for first unpaid invoice reminder |
| `cfg_reminder_delay_2_days` | int | `14` | Days after due date for second reminder |
| `cfg_reminder_delay_3_days` | int | `30` | Days after due date for third reminder |
| `cfg_sms_provider` | string | `` | SMS provider label (e.g. `vonage`) |
| `cfg_sms_api_url` | string | `` | SMS provider base API URL |
| `cfg_sms_api_key` | string | `` | SMS provider API key or bearer token |
| `cfg_sms_from` | string | `` | SMS sender ID or E.164 number |

---

## How runtime changes take effect

```
PUT /api/v1/settings/cfg_kpi_refresh_interval_seconds?garage_id=0
Content-Type: application/json
Authorization: Bearer <admin_token>

{
  "value": "120",
  "description": "Reduced polling interval for high-traffic period"
}
```

The write endpoint:
1. Upserts the row in `garage_setting`.
2. Immediately deletes the Redis cache key `cfg:0:cfg_kpi_refresh_interval_seconds`.
3. The next call to `SettingsService.get_setting("cfg_kpi_refresh_interval_seconds")` reads
   the new value from the DB and re-caches it.

All subsequent reads use the new value without any server restart.

To revert a setting to its environment/default value, call:

```
DELETE /api/v1/settings/cfg_kpi_refresh_interval_seconds?garage_id=0
```

---

## No-hardcoded-values policy

The CI pipeline runs a grep check (`.github/workflows/ci.yml`, job `lint`) that
fails if any Python source file under `backend/app/` contains a numeric or
string literal that matches known threshold patterns (e.g. bare `= 30`,
`= 5`, `= 300`) outside of `config.py` or test files.

See `.github/scripts/check_hardcoded.sh` for the exact rules and exemption list.
