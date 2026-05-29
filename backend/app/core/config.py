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

    # -------------------------------------------------------------------------
    # PDF / Document printing
    # -------------------------------------------------------------------------
    pdf_garage_name: str = "Xpert Garage"
    pdf_garage_address: str = ""
    pdf_garage_phone: str = ""
    pdf_garage_email: str = ""
    pdf_garage_logo_path: str = ""  # absolute path to logo file, or empty
    pdf_vat_number: str = ""
    pdf_legal_mention: str = ""
    pdf_bank_details: str = ""
    pdf_footer_text: str = ""
    pdf_currency_symbol: str = "€"
    pdf_payment_terms: str = "Paiement à 30 jours"

    # -------------------------------------------------------------------------
    # Cash register
    # -------------------------------------------------------------------------
    cash_diff_require_reason: bool = True  # require reason when closing with nonzero difference

    # -------------------------------------------------------------------------
    # Credit limit enforcement
    # -------------------------------------------------------------------------
    credit_limit_mode: str = "block"   # "block" = reject; "warn" = log only
    credit_currency: str = "EUR"       # ISO-4217 currency code used for balance events

    # -------------------------------------------------------------------------
    # Parts / stock
    # -------------------------------------------------------------------------
    cfg_gtk3_dll_dir: str = ""      # Windows only: path to GTK3\bin (e.g. C:\GTK3\bin)
    cfg_allow_negative_stock: bool = False  # allow on-hand to go negative with explicit reason

    # -------------------------------------------------------------------------
    # Purchase orders
    # -------------------------------------------------------------------------
    cfg_po_match_tolerance_percent: float = 5.0  # three-way match tolerance %

    # -------------------------------------------------------------------------
    # Media upload (photo/video for inspections)
    # -------------------------------------------------------------------------
    cfg_upload_chunk_size_bytes: int = 5_242_880   # 5 MB — S3 multipart minimum per part
    cfg_photo_archive_after_days: int = 90          # days after upload before cold-storage move
    cfg_image_max_dimension: int = 1920             # client-side compression target (longest edge, px)
    cfg_image_quality: int = 85                     # client-side JPEG/WebP quality (0-100)
    cfg_media_session_ttl_hours: int = 24           # how long an incomplete upload session stays valid
    s3_bucket_media_archive: str = ""               # bucket for cold storage; falls back to s3_bucket_media

    # -------------------------------------------------------------------------
    # Inspections
    # -------------------------------------------------------------------------
    cfg_inspection_approval_expiry_days: int = 7  # days a customer approval link stays valid

    # -------------------------------------------------------------------------
    # KPI dashboard
    # -------------------------------------------------------------------------
    cfg_kpi_refresh_interval_seconds: int = 300   # live endpoint Redis cache TTL
    cfg_kpi_workshop_capacity: int = 10            # number of bays / concurrent RO slots

    # -------------------------------------------------------------------------
    # Accounting export
    # -------------------------------------------------------------------------
    cfg_accounting_format: str = "generic_csv"  # sage | cegid | ebp | generic_csv

    # -------------------------------------------------------------------------
    # Notifications
    # -------------------------------------------------------------------------
    cfg_notification_max_retries: int = 3
    cfg_quiet_hours_start: str = "22:00"  # HH:MM — start of quiet window
    cfg_quiet_hours_end: str = "08:00"    # HH:MM — end of quiet window (may cross midnight)

    # Scheduled reminder delays (days after due / threshold date)
    cfg_reminder_delay_1_days: int = 7
    cfg_reminder_delay_2_days: int = 14
    cfg_reminder_delay_3_days: int = 30

    # SMS provider (provider-agnostic HTTP)
    cfg_sms_provider: str = ""   # arbitrary label, e.g. "vonage"
    cfg_sms_api_url: str = ""    # base URL for the provider's send endpoint
    cfg_sms_api_key: str = ""    # API key / bearer token
    cfg_sms_from: str = ""       # sender ID or E.164 number


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached application settings instance."""
    return Settings()  # type: ignore[call-arg]
