"""
Core configuration loader.

All tuneable values come from environment variables (infrastructure settings)
or the database settings table (CFG_* runtime values loaded via SettingsService).
No hard-coded defaults for business-logic values.
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=[".env", "../.env"],
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # -------------------------------------------------------------------------
    # Application
    # -------------------------------------------------------------------------
    app_name: str = "Xpert-ERP"
    app_version: str = "0.1.0"
    environment: str = "development"
    debug: bool = False

    # -------------------------------------------------------------------------
    # Database
    # -------------------------------------------------------------------------
    database_url: str  # e.g. postgresql+asyncpg://user:pass@localhost:5432/xpert_erp
    database_pool_size: int = 10
    database_max_overflow: int = 20
    database_echo: bool = False

    # -------------------------------------------------------------------------
    # Redis
    # -------------------------------------------------------------------------
    redis_url: str  # e.g. redis://localhost:6379/0

    # -------------------------------------------------------------------------
    # Object storage (S3-compatible / MinIO)
    # -------------------------------------------------------------------------
    s3_endpoint_url: str
    s3_access_key_id: str
    s3_secret_access_key: str
    s3_bucket_documents: str
    s3_bucket_media: str
    s3_region: str = "us-east-1"

    # -------------------------------------------------------------------------
    # Security
    # -------------------------------------------------------------------------
    secret_key: str  # used for signing JWT access tokens
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    auth_max_failed_attempts: int = 5
    auth_lockout_minutes: int = 15
    password_reset_expiry_minutes: int = 30
    password_min_length: int = 8

    # -------------------------------------------------------------------------
    # CORS
    # -------------------------------------------------------------------------
    allowed_origins: list[str] = ["http://localhost:5173"]

    # -------------------------------------------------------------------------
    # Logging
    # -------------------------------------------------------------------------
    log_level: str = "INFO"
    log_dir: str = "logs"
    log_max_bytes: int = 10_485_760  # 10 MB
    log_backup_count: int = 5

    # -------------------------------------------------------------------------
    # Email (SMTP)
    # -------------------------------------------------------------------------
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    smtp_from_address: str = ""
    smtp_from_name: str = "Xpert-ERP"

    # -------------------------------------------------------------------------
    # Document upload (CFG_* runtime tunables backed by env for now)
    # -------------------------------------------------------------------------
    max_upload_size_bytes: int = 10_485_760  # 10 MB
    allowed_mime_types: list[str] = [
        "application/pdf",
        "image/jpeg",
        "image/png",
        "image/webp",
    ]
    signed_url_expiry_seconds: int = 3600  # 1 hour


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached application settings instance."""
    return Settings()  # type: ignore[call-arg]
