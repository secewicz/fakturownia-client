"""Python client for the Fakturownia (InvoiceOcean) REST API."""

from ._retry import RetryPolicy
from ._version import __version__
from .async_client import AsyncFakturowniaClient
from .client import FakturowniaClient, normalize_domain
from .exceptions import (
    AuthenticationError,
    BadRequestError,
    FakturowniaError,
    NotFoundError,
    RateLimitError,
    ResponseParseError,
    ServerError,
    TransportError,
    ValidationError,
)
from .models import (
    ApiRecord,
    Client,
    Invoice,
    InvoiceCreate,
    InvoiceKind,
    InvoicePosition,
    InvoicePositionCreate,
    InvoiceStatus,
    Payment,
    Product,
)

__all__ = [
    "AsyncFakturowniaClient",
    "ApiRecord",
    "AuthenticationError",
    "BadRequestError",
    "Client",
    "FakturowniaClient",
    "FakturowniaError",
    "Invoice",
    "InvoiceCreate",
    "InvoiceKind",
    "InvoicePosition",
    "InvoicePositionCreate",
    "InvoiceStatus",
    "NotFoundError",
    "Payment",
    "Product",
    "RateLimitError",
    "ResponseParseError",
    "RetryPolicy",
    "ServerError",
    "TransportError",
    "ValidationError",
    "__version__",
    "normalize_domain",
]
