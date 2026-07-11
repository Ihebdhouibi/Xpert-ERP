"""
Notification adapter interface and concrete implementations.

Adapters receive pre-rendered subject + body; template rendering lives in
service.py so the DB-stored Jinja2 templates are the single source of truth.

Credentials (SMTP password, SMS API key) are read from settings at call time
and are never written to logs or included in DeliveryResult fields.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Optional

import aiosmtplib
import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class DeliveryResult:
    success: bool
    provider_reference: Optional[str] = field(default=None)
    error: Optional[str] = field(default=None)


@dataclass
class EmailAttachment:
    filename: str
    content: bytes
    mimetype: str = "application/pdf"


# ---------------------------------------------------------------------------
# Abstract interface
# ---------------------------------------------------------------------------


class NotificationAdapter(ABC):
    @abstractmethod
    async def send(
        self,
        recipient: str,
        channel: str,
        subject: Optional[str],
        body: str,
        attachments: Optional[list[EmailAttachment]] = None,
    ) -> DeliveryResult:
        """Send a pre-rendered notification and return a DeliveryResult."""


# ---------------------------------------------------------------------------
# Email adapter — aiosmtplib
# ---------------------------------------------------------------------------


class EmailAdapter(NotificationAdapter):
    async def send(
        self,
        recipient: str,
        channel: str,
        subject: Optional[str],
        body: str,
        attachments: Optional[list[EmailAttachment]] = None,
    ) -> DeliveryResult:
        settings = get_settings()

        if attachments:
            message: MIMEMultipart = MIMEMultipart("mixed")
            alt_part = MIMEMultipart("alternative")
            alt_part.attach(MIMEText(body, "html", "utf-8"))
            message.attach(alt_part)
            for att in attachments:
                part = MIMEApplication(att.content, _subtype=att.mimetype.split("/")[-1])
                part.add_header("Content-Disposition", "attachment", filename=att.filename)
                message.attach(part)
        else:
            message = MIMEMultipart("alternative")
            message.attach(MIMEText(body, "html", "utf-8"))

        message["From"] = f"{settings.smtp_from_name} <{settings.smtp_from_address}>"
        message["To"] = recipient
        message["Subject"] = subject or ""

        try:
            await aiosmtplib.send(
                message,
                hostname=settings.smtp_host,
                port=settings.smtp_port,
                username=settings.smtp_username or None,
                password=settings.smtp_password or None,
                start_tls=settings.smtp_use_tls,
            )
        except Exception as exc:
            logger.warning("email_send_failed: %s to %s", type(exc).__name__, recipient)
            return DeliveryResult(success=False, error=type(exc).__name__)

        return DeliveryResult(success=True)


# ---------------------------------------------------------------------------
# SMS adapter — provider-agnostic HTTP POST
# ---------------------------------------------------------------------------


class SmsAdapter(NotificationAdapter):
    async def send(
        self,
        recipient: str,
        channel: str,
        subject: Optional[str],
        body: str,
        attachments: Optional[list[EmailAttachment]] = None,
    ) -> DeliveryResult:
        settings = get_settings()

        if not settings.cfg_sms_api_url:
            return DeliveryResult(success=False, error="sms_provider_not_configured")

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    settings.cfg_sms_api_url,
                    json={
                        "from": settings.cfg_sms_from,
                        "to": recipient,
                        "text": body,
                    },
                    headers={"Authorization": f"Bearer {settings.cfg_sms_api_key}"},
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "sms_send_failed",
                http_status=exc.response.status_code,
                recipient=recipient,
            )
            return DeliveryResult(success=False, error=f"http_{exc.response.status_code}")
        except Exception as exc:
            logger.warning("sms_send_failed", exc_type=type(exc).__name__, recipient=recipient)
            return DeliveryResult(success=False, error=type(exc).__name__)

        data: dict[str, Any] = {}
        try:
            data = response.json()
        except Exception:
            pass

        ref: Optional[str] = (
            data.get("message_id") or data.get("id") or str(response.status_code)
        )
        return DeliveryResult(success=True, provider_reference=ref)
