# Environment Variables Reference

All variables read from `.env` in the project root. Required vars have no default.

## Application

| Variable | Default | Production value | Notes |
|---|---|---|---|
| `ENVIRONMENT` | `development` | `production` | Controls docs_url, log verbosity |
| `DEBUG` | `false` | `false` | Never true in prod |
| `APP_VERSION` | `0.1.0` | bump per release | |

## Database

| Variable | Default | Notes |
|---|---|---|
| `DATABASE_URL` | required | `postgresql+asyncpg://user:pass@db:5432/dbname` |
| `DATABASE_ECHO` | `true` | **Set to `false` in production** — dev default logs every SQL query |
| `DATABASE_POOL_SIZE` | `10` | Connections per worker |

## Redis

| Variable | Default | Notes |
|---|---|---|
| `REDIS_URL` | required | `redis://:password@redis:6379/0` |

## Object Storage

| Variable | Default | Notes |
|---|---|---|
| `S3_ENDPOINT_URL` | required | Internal: `http://minio:9000` |
| `S3_PUBLIC_ENDPOINT_URL` | `""` (falls back to S3_ENDPOINT_URL) | **Must be set in prod** — browser-accessible URL for presigned links |
| `S3_BUCKET_DOCUMENTS` | required | e.g. `xpert-documents` |
| `S3_BUCKET_MEDIA` | required | e.g. `xpert-media` |

## Security

| Variable | Default | Notes |
|---|---|---|
| `SECRET_KEY` | required | **Generate fresh for each environment** — `python -c "import secrets; print(secrets.token_hex(64))"` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | JWT expiry |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Refresh token expiry |
| `ALLOWED_ORIGINS` | `["http://localhost:5173"]` | **Must match your production domain** exactly |

## Logging

| Variable | Default | Production value | Notes |
|---|---|---|---|
| `LOG_LEVEL` | `DEBUG` | `WARNING` | Dev default is very verbose — change for prod |
| `LOG_DIR` | `logs` | `logs` | Relative to working dir |

## Email

| Variable | Default | Notes |
|---|---|---|
| `SMTP_HOST` | `""` | Required for email features |
| `SMTP_PORT` | `587` | |
| `SMTP_USE_TLS` | `true` | |
| `SMTP_FROM_ADDRESS` | required | e.g. `noreply@motors-utilitaires.fr` |
| `CFG_ADMIN_NOTIFICATION_EMAILS` | `""` | Comma-separated admin email(s) for alerts |

## Frontend / CORS

| Variable | Default | Production value |
|---|---|---|
| `FRONTEND_BASE_URL` | `http://localhost:5173` | `https://motors-utilitaires.fr` |
| `ALLOWED_ORIGINS` | `["http://localhost:5173"]` | `["https://motors-utilitaires.fr"]` |

## OCR

| Variable | Default | Notes |
|---|---|---|
| `CFG_OCR_ENGINE` | `onnx` | `onnx` (slim) or `paddle` (full) |
| `CFG_OCR_USE_TEXTLINE_ORIENTATION` | `false` | Adds ~70 MB RAM + ~0.2s/scan — only enable if needed |

## Business logic

| Variable | Default | Notes |
|---|---|---|
| `CREDIT_LIMIT_MODE` | `block` | `block` or `warn` |
| `PDF_GARAGE_LOGO_PATH` | `/app/assets/logo.png` | Path inside the Docker container |
