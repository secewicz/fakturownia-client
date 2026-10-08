"""Asynchronous client for the Fakturownia (InvoiceOcean) REST API.

Same endpoints, models, exceptions, retry policy and auth rules as
:class:`fakturownia_client.FakturowniaClient` (token only in the
``Authorization: Bearer`` header), built on ``httpx.AsyncClient``.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator, Sequence
from types import TracebackType
from typing import Any, TypeVar

import httpx

from . import _ops
from ._base import DEFAULT_TIMEOUT, Timeout, auth_headers, base_url
from ._retry import RetryPolicy
from .client import _check_pdf, _parse
from .exceptions import TransportError, _retry_after_seconds, raise_for_status
from .models import ApiRecord, Client, Invoice, InvoiceCreate, InvoiceStatus, Payment, Product
from .pagination import MAX_PER_PAGE, aiter_pages

__all__ = ["AsyncFakturowniaClient"]

logger = logging.getLogger(__name__)

T = TypeVar("T")


class AsyncFakturowniaClient:
    """Async twin of :class:`fakturownia_client.FakturowniaClient`."""

    def __init__(
        self,
        domain: str,
        api_token: str,
        *,
        timeout: Timeout = DEFAULT_TIMEOUT,
        max_retries: int = 3,
        retry_policy: RetryPolicy | None = None,
        verify: bool = True,
        limits: httpx.Limits | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url(domain)
        self._retry = retry_policy or RetryPolicy(max_retries=max_retries)
        self._http = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout,
            transport=transport,
            verify=verify,
            limits=limits or httpx.Limits(),
            follow_redirects=True,
            headers=auth_headers(api_token),
        )

    # -- lifecycle -----------------------------------------------------------

    async def close(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> AsyncFakturowniaClient:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.close()

    # -- transport -----------------------------------------------------------

    async def _send(self, op: _ops.Op[T], params: dict[str, Any]) -> httpx.Response:
        attempt = 0
        while True:
            try:
                response = await self._http.request(
                    op.method, op.path, params=params, json=op.json_body
                )
            except httpx.HTTPError as exc:
                if not self._retry.should_retry(attempt, None):
                    raise TransportError(f"{op.method} {op.path}: {exc}") from exc
                delay = self._retry.delay(attempt)
                logger.info(
                    "%s %s transport error, retry in %.1fs: %s", op.method, op.path, delay, exc
                )
            else:
                if not self._retry.should_retry(attempt, response.status_code):
                    return response
                retry_after = (
                    _retry_after_seconds(response) if response.status_code == 429 else None
                )
                delay = self._retry.delay(attempt, retry_after=retry_after)
                logger.info(
                    "%s %s -> %s, retry in %.1fs", op.method, op.path, response.status_code, delay
                )
            await asyncio.sleep(delay)
            attempt += 1

    async def _execute(self, op: _ops.Op[T]) -> T:
        params = {k: v for k, v in op.params.items() if v is not None}
        start = time.monotonic()
        response = await self._send(op, params)
        logger.debug(
            "%s %s -> %s (%.0f ms)",
            op.method,
            op.path,
            response.status_code,
            (time.monotonic() - start) * 1000,
        )
        raise_for_status(response)
        return _parse(op, response)

    # -- invoices --------------------------------------------------------------

    async def list_invoices(
        self,
        *,
        period: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        client_id: int | None = None,
        number: str | None = None,
        kind: str | None = None,
        income: bool | None = None,
        include_positions: bool = False,
        order: str | None = None,
        page: int = 1,
        per_page: int = 25,
    ) -> list[Invoice]:
        """``GET /invoices.json``; ``date_from``/``date_to`` imply ``period="more"``.

        ``income``: None (default) lists sales invoices, ``False`` lists
        cost/expense invoices (``income=no``), ``True`` forces sales explicitly.
        """
        return await self._execute(
            _ops.list_invoices(
                period=period,
                date_from=date_from,
                date_to=date_to,
                client_id=client_id,
                number=number,
                kind=kind,
                income=income,
                include_positions=include_positions,
                order=order,
                page=page,
                per_page=per_page,
            )
        )

    def iter_invoices(self, **filters: Any) -> AsyncIterator[Invoice]:
        filters.pop("page", None)
        filters.pop("per_page", None)

        async def fetch(page: int) -> list[Invoice]:
            return await self.list_invoices(page=page, per_page=MAX_PER_PAGE, **filters)

        return aiter_pages(fetch)

    async def get_invoice(self, invoice_id: int) -> Invoice:
        return await self._execute(_ops.get_invoice(invoice_id))

    async def create_invoice(self, invoice: InvoiceCreate | dict[str, Any]) -> Invoice:
        return await self._execute(_ops.create_invoice(invoice))

    async def update_invoice(self, invoice_id: int, fields: dict[str, Any]) -> Invoice:
        return await self._execute(_ops.update_invoice(invoice_id, fields))

    async def delete_invoice(self, invoice_id: int) -> None:
        """Permanently delete an invoice — destructive, prefer status changes."""
        await self._execute(_ops.delete_invoice(invoice_id))

    async def change_invoice_status(self, invoice_id: int, status: InvoiceStatus) -> Any:
        """Raises :class:`FakturowniaError` when the API answers 200 with an error envelope."""
        return await self._execute(_ops.change_invoice_status(invoice_id, status))

    async def download_invoice_pdf(self, invoice_id: int) -> bytes:
        content: bytes = await self._execute(_ops.download_invoice_pdf(invoice_id))
        _check_pdf(content)
        return content

    async def send_invoice_by_email(
        self,
        invoice_id: int,
        *,
        email_to: str | Sequence[str] | None = None,
        email_cc: str | Sequence[str] | None = None,
        email_pdf: bool | None = None,
        print_option: str | None = None,
        update_buyer_email: bool | None = None,
    ) -> Any:
        """E-mail the invoice to its buyer (or to ``email_to`` — max 5 addresses).

        ``print_option``: ``original`` / ``copy`` / ``original_and_copy`` /
        ``duplicate``. Raises :class:`FakturowniaError` on the API's
        ``200 + {"code": "error"}`` envelope.
        """
        return await self._execute(
            _ops.send_invoice_by_email(
                invoice_id,
                email_to=email_to,
                email_cc=email_cc,
                email_pdf=email_pdf,
                print_option=print_option,
                update_buyer_email=update_buyer_email,
            )
        )

    # -- clients ---------------------------------------------------------------

    async def list_clients(
        self,
        *,
        name: str | None = None,
        tax_no: str | None = None,
        email: str | None = None,
        external_id: str | None = None,
        page: int = 1,
        per_page: int = 25,
    ) -> list[Client]:
        return await self._execute(
            _ops.list_clients(
                name=name,
                tax_no=tax_no,
                email=email,
                external_id=external_id,
                page=page,
                per_page=per_page,
            )
        )

    def iter_clients(self, **filters: Any) -> AsyncIterator[Client]:
        filters.pop("page", None)
        filters.pop("per_page", None)

        async def fetch(page: int) -> list[Client]:
            return await self.list_clients(page=page, per_page=MAX_PER_PAGE, **filters)

        return aiter_pages(fetch)

    async def get_client(self, client_id: int) -> Client:
        return await self._execute(_ops.get_client(client_id))

    async def create_client(self, client: dict[str, Any]) -> Client:
        return await self._execute(_ops.create_client(client))

    async def update_client(self, client_id: int, fields: dict[str, Any]) -> Client:
        return await self._execute(_ops.update_client(client_id, fields))

    async def delete_client(self, client_id: int) -> None:
        await self._execute(_ops.delete_client(client_id))

    # -- payments (banking) -------------------------------------------------------

    async def list_payments(
        self, *, page: int = 1, per_page: int = 25, include_invoices: bool = False
    ) -> list[Payment]:
        """``GET /banking/payments.json``; ``include_invoices`` embeds linked invoices."""
        return await self._execute(
            _ops.list_payments(page=page, per_page=per_page, include_invoices=include_invoices)
        )

    def iter_payments(self, **filters: Any) -> AsyncIterator[Payment]:
        filters.pop("page", None)
        filters.pop("per_page", None)

        async def fetch(page: int) -> list[Payment]:
            return await self.list_payments(page=page, per_page=MAX_PER_PAGE, **filters)

        return aiter_pages(fetch)

    async def get_payment(self, payment_id: int) -> Payment:
        return await self._execute(_ops.get_payment(payment_id))

    async def create_payment(self, payment: dict[str, Any]) -> Payment:
        """Record a payment; link it via ``invoice_id`` or ``invoice_ids`` (settled in order)."""
        return await self._execute(_ops.create_payment(payment))

    async def update_payment(self, payment_id: int, fields: dict[str, Any]) -> Payment:
        return await self._execute(_ops.update_payment(payment_id, fields))

    async def delete_payment(self, payment_id: int) -> None:
        await self._execute(_ops.delete_payment(payment_id))

    # -- products ----------------------------------------------------------------

    async def list_products(self, *, page: int = 1, per_page: int = 25) -> list[Product]:
        return await self._execute(_ops.list_products(page=page, per_page=per_page))

    def iter_products(self, **filters: Any) -> AsyncIterator[Product]:
        filters.pop("page", None)
        filters.pop("per_page", None)

        async def fetch(page: int) -> list[Product]:
            return await self.list_products(page=page, per_page=MAX_PER_PAGE, **filters)

        return aiter_pages(fetch)

    async def get_product(self, product_id: int) -> Product:
        return await self._execute(_ops.get_product(product_id))

    async def create_product(self, product: dict[str, Any]) -> Product:
        return await self._execute(_ops.create_product(product))

    async def update_product(self, product_id: int, fields: dict[str, Any]) -> Product:
        return await self._execute(_ops.update_product(product_id, fields))

    async def delete_product(self, product_id: int) -> None:
        """Undocumented endpoint — the official API README lists no product DELETE."""
        await self._execute(_ops.delete_product(product_id))

    # -- additional read-only resources ---------------------------------------

    async def list_recurrings(self, *, page: int = 1, per_page: int = 25) -> list[ApiRecord]:
        return await self._execute(_ops.list_recurrings(page=page, per_page=per_page))

    async def get_recurring(self, recurring_id: int) -> ApiRecord:
        return await self._execute(_ops.get_recurring(recurring_id))

    async def list_price_lists(self, *, page: int = 1, per_page: int = 25) -> list[ApiRecord]:
        return await self._execute(_ops.list_price_lists(page=page, per_page=per_page))

    async def get_price_list(self, price_list_id: int) -> ApiRecord:
        return await self._execute(_ops.get_price_list(price_list_id))

    async def list_warehouses(self, *, page: int = 1, per_page: int = 25) -> list[ApiRecord]:
        return await self._execute(_ops.list_warehouses(page=page, per_page=per_page))

    async def get_warehouse(self, warehouse_id: int) -> ApiRecord:
        return await self._execute(_ops.get_warehouse(warehouse_id))

    async def list_warehouse_documents(
        self, *, page: int = 1, per_page: int = 25
    ) -> list[ApiRecord]:
        return await self._execute(_ops.list_warehouse_documents(page=page, per_page=per_page))

    async def get_warehouse_document(self, warehouse_document_id: int) -> ApiRecord:
        return await self._execute(_ops.get_warehouse_document(warehouse_document_id))

    async def list_warehouse_actions(
        self,
        *,
        warehouse_id: int | None = None,
        kind: str | None = None,
        product_id: int | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        from_warehouse_document: int | None = None,
        to_warehouse_document: int | None = None,
        warehouse_document_id: int | None = None,
        page: int = 1,
        per_page: int = 25,
    ) -> list[ApiRecord]:
        return await self._execute(
            _ops.list_warehouse_actions(
                warehouse_id=warehouse_id,
                kind=kind,
                product_id=product_id,
                date_from=date_from,
                date_to=date_to,
                from_warehouse_document=from_warehouse_document,
                to_warehouse_document=to_warehouse_document,
                warehouse_document_id=warehouse_document_id,
                page=page,
                per_page=per_page,
            )
        )

    async def list_categories(self, *, page: int = 1, per_page: int = 25) -> list[ApiRecord]:
        return await self._execute(_ops.list_categories(page=page, per_page=per_page))

    async def get_category(self, category_id: int) -> ApiRecord:
        return await self._execute(_ops.get_category(category_id))

    async def list_departments(self, *, page: int = 1, per_page: int = 25) -> list[ApiRecord]:
        return await self._execute(_ops.list_departments(page=page, per_page=per_page))

    async def get_department(self, department_id: int) -> ApiRecord:
        return await self._execute(_ops.get_department(department_id))

    async def list_issuers(self, *, page: int = 1, per_page: int = 25) -> list[ApiRecord]:
        return await self._execute(_ops.list_issuers(page=page, per_page=per_page))

    async def get_issuer(self, issuer_id: int) -> ApiRecord:
        return await self._execute(_ops.get_issuer(issuer_id))

    async def list_bank_accounts(self, *, page: int = 1, per_page: int = 25) -> list[ApiRecord]:
        return await self._execute(_ops.list_bank_accounts(page=page, per_page=per_page))

    async def get_bank_account(self, bank_account_id: int) -> ApiRecord:
        return await self._execute(_ops.get_bank_account(bank_account_id))

    async def list_webhooks(self, *, page: int = 1, per_page: int = 25) -> list[ApiRecord]:
        return await self._execute(_ops.list_webhooks(page=page, per_page=per_page))

    async def get_webhook(self, webhook_id: int) -> ApiRecord:
        return await self._execute(_ops.get_webhook(webhook_id))
