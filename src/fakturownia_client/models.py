"""Pydantic models for Fakturownia API resources.

The API returns dozens of fields per resource; the important ones are typed
below and everything else stays reachable thanks to ``extra="allow"``.
Prices arrive as strings (e.g. ``"89.0"``) and are kept as strings to avoid
float rounding on money values.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

InvoiceStatus = Literal["issued", "sent", "paid", "partial", "rejected"]
InvoiceKind = Literal[
    "vat", "proforma", "correction", "receipt", "advance", "final", "estimate", "invoice"
]


class _ApiModel(BaseModel):
    model_config = ConfigDict(extra="allow")


def _blank_to_none(value: object) -> object:
    """Fakturownia returns "" for unset dates; treat it as absent."""
    return None if value == "" else value


class ApiRecord(_ApiModel):
    """Generic read-only API resource with stable common fields."""

    id: int
    name: str | None = None


class InvoicePosition(_ApiModel):
    id: int | None = None
    name: str | None = None
    description: str | None = None
    quantity: float | str | None = None
    quantity_unit: str | None = None
    tax: str | float | None = None
    price_net: str | None = None
    price_gross: str | None = None
    total_price_net: str | None = None
    total_price_gross: str | None = None
    product_id: int | None = None


class Invoice(_ApiModel):
    id: int
    number: str | None = None
    kind: str | None = None
    status: str | None = None
    issue_date: date | None = None
    sell_date: date | str | None = None
    payment_to: date | None = None
    paid_date: date | None = None
    seller_name: str | None = None
    seller_tax_no: str | None = None
    buyer_name: str | None = None
    buyer_tax_no: str | None = None
    buyer_email: str | None = None
    client_id: int | None = None
    price_net: str | None = None
    price_gross: str | None = None
    currency: str | None = None
    paid: str | None = None
    positions: list[InvoicePosition] | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    _blank_dates = field_validator(
        "issue_date",
        "sell_date",
        "payment_to",
        "paid_date",
        "created_at",
        "updated_at",
        mode="before",
    )(_blank_to_none)


class InvoicePositionCreate(_ApiModel):
    name: str
    quantity: float = 1
    tax: str | float = 23
    price_net: str | float | None = None
    price_gross: str | float | None = None
    total_price_gross: str | float | None = None
    product_id: int | None = None


class InvoiceCreate(_ApiModel):
    kind: str = "vat"
    number: str | None = None
    issue_date: date | None = None
    sell_date: date | None = None
    payment_to: date | None = None
    seller_name: str | None = None
    seller_tax_no: str | None = None
    buyer_name: str | None = None
    buyer_tax_no: str | None = None
    buyer_email: str | None = None
    client_id: int | None = None
    positions: list[InvoicePositionCreate] = []


class Client(_ApiModel):
    id: int
    name: str | None = None
    tax_no: str | None = None
    email: str | None = None
    phone: str | None = None
    street: str | None = None
    city: str | None = None
    post_code: str | None = None
    country: str | None = None
    external_id: str | None = None
    company: bool | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    _blank_dates = field_validator("created_at", "updated_at", mode="before")(_blank_to_none)


class Payment(_ApiModel):
    """A banking payment (``/banking/payments``), optionally linked to invoices.

    ``invoices`` is populated only when listing with ``include=invoices``.
    """

    id: int
    name: str | None = None
    price: str | float | None = None
    currency: str | None = None
    paid: bool | None = None
    kind: str | None = None
    invoice_id: int | None = None
    client_id: int | None = None
    description: str | None = None
    paid_date: datetime | None = None  # full timestamp on the live API, not a date
    created_at: datetime | None = None
    updated_at: datetime | None = None
    invoices: list[Invoice] | None = None

    _blank_dates = field_validator("paid_date", "created_at", "updated_at", mode="before")(
        _blank_to_none
    )


class Product(_ApiModel):
    id: int
    name: str | None = None
    code: str | None = None
    description: str | None = None
    price_net: str | None = None
    price_gross: str | None = None
    tax: str | float | None = None
    currency: str | None = None
    quantity: float | str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    _blank_dates = field_validator("created_at", "updated_at", mode="before")(_blank_to_none)
