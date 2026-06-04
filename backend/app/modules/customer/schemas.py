from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.modules.customer.models import (
    ContactChannel,
    CustomerStatus,
    CustomerType,
)

# ---------------------------------------------------------------------------
# Shared validators
# ---------------------------------------------------------------------------

_E164_PATTERN = r"^\+[1-9]\d{6,14}$"
_CURRENCY_PATTERN = r"^[A-Z]{3}$"


def _normalize_e164(value: Optional[str]) -> Optional[str]:
    """Trim whitespace and reject empty strings. Format is enforced by Field pattern."""
    if value is None:
        return None
    v = value.strip()
    return v or None


# ---------------------------------------------------------------------------
# Nested value objects
# ---------------------------------------------------------------------------


class AddressSchema(BaseModel):
    street: Optional[str] = Field(None, max_length=255)
    city: Optional[str] = Field(None, max_length=100)
    postal_code: Optional[str] = Field(None, max_length=20)
    country: Optional[str] = Field(None, max_length=100)


class CustomerContactCreate(BaseModel):
    channel: ContactChannel
    value: str = Field(min_length=1, max_length=255)
    label: Optional[str] = Field(None, max_length=100)
    is_primary: bool = False


class CustomerContactSummary(BaseModel):
    id: int
    channel: ContactChannel
    value: str
    label: Optional[str]
    is_primary: bool

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Customer requests
# ---------------------------------------------------------------------------


class CustomerCreateRequest(BaseModel):
    type: CustomerType
    full_name: str = Field(min_length=1, max_length=255)
    company_name: Optional[str] = Field(None, min_length=1, max_length=255)
    fiscal_id: Optional[str] = Field(None, min_length=1, max_length=50)
    email: Optional[EmailStr] = None
    phone_e164: Optional[str] = Field(None, pattern=_E164_PATTERN, max_length=20)
    address: Optional[AddressSchema] = None
    segment: Optional[str] = Field(None, max_length=50)
    credit_limit_minor: int = Field(0, ge=0)
    credit_currency: Optional[str] = Field(None, pattern=_CURRENCY_PATTERN)
    notes: Optional[str] = Field(None, max_length=10_000)
    contacts: list[CustomerContactCreate] = Field(default_factory=list)

    _normalize_phone = field_validator("phone_e164", mode="before")(
        classmethod(lambda cls, v: _normalize_e164(v))  # noqa: ARG005
    )

    @model_validator(mode="after")
    def _company_must_have_name(self) -> "CustomerCreateRequest":
        if self.type == CustomerType.company and not self.company_name:
            raise ValueError("company_name is required when type is 'company'")
        return self

    @model_validator(mode="after")
    def _credit_limit_requires_currency(self) -> "CustomerCreateRequest":
        if self.credit_limit_minor > 0 and not self.credit_currency:
            raise ValueError("credit_currency is required when credit_limit_minor > 0")
        return self


class CustomerUpdateRequest(BaseModel):
    """All fields optional; `version` is required for optimistic locking.

    Credit limit changes are NOT accepted here — they use a separate endpoint
    (`POST /customers/{id}/credit-limit`) gated by `customer.credit_limit.update`.
    """

    version: int = Field(ge=1)
    full_name: Optional[str] = Field(None, min_length=1, max_length=255)
    company_name: Optional[str] = Field(None, max_length=255)
    fiscal_id: Optional[str] = Field(None, min_length=1, max_length=50)
    email: Optional[EmailStr] = None
    phone_e164: Optional[str] = Field(None, pattern=_E164_PATTERN, max_length=20)
    address: Optional[AddressSchema] = None
    segment: Optional[str] = Field(None, max_length=50)
    status: Optional[CustomerStatus] = None
    notes: Optional[str] = Field(None, max_length=10_000)

    _normalize_phone = field_validator("phone_e164", mode="before")(
        classmethod(lambda cls, v: _normalize_e164(v))  # noqa: ARG005
    )


class CreditLimitUpdateRequest(BaseModel):
    credit_limit_minor: int = Field(ge=0)
    credit_currency: str = Field(pattern=_CURRENCY_PATTERN)
    reason: str = Field(min_length=1, max_length=500)


# ---------------------------------------------------------------------------
# Customer responses
# ---------------------------------------------------------------------------


class CustomerSummary(BaseModel):
    id: str  # public_id (UUID as string)
    int_id: int  # internal integer PK — used by cross-module FKs (e.g. vehicle.customer_id)
    garage_id: int
    type: CustomerType
    full_name: str
    company_name: Optional[str]
    email: Optional[str]
    phone_e164: Optional[str]
    status: CustomerStatus
    segment: Optional[str]
    credit_limit_minor: int
    credit_currency: Optional[str]
    outstanding_minor: int
    last_visit_at: Optional[datetime]
    created_at: datetime


class CustomerDetail(CustomerSummary):
    fiscal_id: Optional[str]
    address: Optional[dict[str, Any]]
    loyalty_points: int
    notes: Optional[str]
    version: int
    updated_at: datetime
    contacts: list[CustomerContactSummary] = Field(default_factory=list)


class CustomerListResponse(BaseModel):
    items: list[CustomerSummary]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Duplicate detection (merge prompt)
# ---------------------------------------------------------------------------


class MergeMatchReason:
    """Reasons used in MergePromptResponse.match_reason.

    Per the M2 spec: a merge prompt fires when `fiscal_id` matches an existing
    customer AND either `phone_e164` or `email` also matches the same row.
    `fiscal_id_only` is included for the edge case where fiscal_id alone
    collides (DB partial unique would also block; we surface a clean response).
    """

    PHONE_AND_FISCAL_ID = "phone_and_fiscal_id"
    EMAIL_AND_FISCAL_ID = "email_and_fiscal_id"
    FISCAL_ID_ONLY = "fiscal_id_only"


class MergePromptResponse(BaseModel):
    code: Literal["duplicate_customer"] = "duplicate_customer"
    match_reason: Literal[
        "phone_and_fiscal_id",
        "email_and_fiscal_id",
        "fiscal_id_only",
    ]
    existing: CustomerSummary


# ---------------------------------------------------------------------------
# Balance ledger
# ---------------------------------------------------------------------------


class CustomerBalanceEventSummary(BaseModel):
    id: int
    reason: str
    delta_minor: int
    currency: str
    ref_type: Optional[str]
    ref_id: Optional[int]
    occurred_at: datetime

    model_config = {"from_attributes": True}


class CustomerBalanceEventCreateRequest(BaseModel):
    """Manual ledger adjustment.

    Invoice / payment modules (M5 / M6) post their own events via the service
    layer and never hit this endpoint.
    """

    reason: str = Field(min_length=1, max_length=50)
    delta_minor: int  # signed: positive = customer owes us, negative = credit
    currency: str = Field(pattern=_CURRENCY_PATTERN)
    note: Optional[str] = Field(None, max_length=500)


class CustomerBalanceEventListResponse(BaseModel):
    items: list[CustomerBalanceEventSummary]
    total: int
    page: int
    page_size: int
