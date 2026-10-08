# Changelog

All notable changes to this project are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/), versioning: SemVer.

## [Unreleased]

## [0.3.0] - 2026-10-08

### Added
- Read-only list/get support in both sync and async clients for recurring
  definitions, price lists, warehouses, warehouse documents, categories,
  departments, issuers, bank accounts, and webhooks.
- Filtered `list_warehouse_actions` support for warehouse, kind, product, date,
  and warehouse-document filters.

## [0.2.1] - 2026-07-31

### Fixed
- `get_payment` now uses `/banking/payments/{id}.json` (plural). The official
  docs show a singular path, but the live API returns 404 for it (verified
  against a real account).
- `Payment.paid_date` is a full `datetime` — the API returns a timestamp, not
  a date, which previously failed model validation.

## [0.2.0] - 2026-07-31

### Added
- Payments (banking) support in both clients: `list_payments`
  (`include_invoices=True` embeds linked invoices), `get_payment`,
  `create_payment` (link via `invoice_id` or `invoice_ids`, settled in array
  order), `update_payment`, `delete_payment`, plus `iter_payments` /
  `aiter_payments` pagination and the `Payment` model.
- `send_invoice_by_email` on both clients: e-mails an invoice to its buyer or
  to explicit recipients (`email_to` accepts a list or a comma-separated
  string; the API caps it at 5 addresses), with `email_cc`, `email_pdf`,
  `print_option` (`original`/`copy`/`original_and_copy`/`duplicate`) and
  `update_buyer_email`. Rejects the API's `200 + {"code": "error"}` envelope.

## [0.1.3] - 2026-07-30

### Added
- "Compatible platforms" documentation and keywords: fakturownia.pl,
  invoiceocean.com, invoiceocean.de, vosfactures.fr, bitfactura.es (regional
  brands of the same API — pass the full account domain).

## [0.1.2] - 2026-07-28

### Changed
- Made the unofficial status explicit everywhere (README, package
  descriptions, alias): this project is not affiliated with or endorsed by
  Fakturownia sp. z o.o. / InvoiceOcean; trademarks are used only to
  indicate compatibility.

## [0.1.1] - 2026-07-28

### Fixed
- `normalize_domain` no longer mangles non-default hosts: anything containing
  a dot is used as-is, so InvoiceOcean and regional domains work
  (`mycompany.invoiceocean.com`). Previously `.fakturownia.pl` was appended
  to every host.

### Added
- Companion (unofficial) alias package [`invoiceocean-client`](https://pypi.org/project/invoiceocean-client/)
  (re-exports the full API with `InvoiceOceanClient`/`AsyncInvoiceOceanClient`
  aliases), published in lockstep from this repository.

## [0.1.0] - 2026-07-28

### Added
- Automatic retries with exponential backoff and jitter on 429/5xx and
  transport errors; `Retry-After` is honoured. Configurable via
  `max_retries` or a custom `RetryPolicy`.
- New exceptions: `BadRequestError` (400, subclass of `ValidationError`),
  `TransportError` (network failures), `ResponseParseError` (unparseable
  2xx bodies). All exceptions now carry the `httpx.Response`;
  `RateLimitError` exposes `retry_after`.
- DEBUG/INFO logging (`logging.getLogger("fakturownia_client.*")`) — never
  includes the API token.
- `User-Agent: fakturownia-client/<version>` header.
- `timeout` accepts `httpx.Timeout`; new `verify` and `limits` passthroughs.
- Async pagination helper `aiter_pages`; `iter_products` accepts filters.

### Fixed
- PDF downloads now follow redirects and validate the `%PDF` signature —
  previously a 302 response body could be silently saved as a "PDF".
- `change_invoice_status` raises on the API's `200 + {"code": "error"}`
  envelope instead of reporting success.
- Blank date strings (`""`) in API responses parse as `None` instead of
  failing the whole page.
- Pagination aborts with a clear error if the API ignores the `page`
  parameter (previously an infinite loop).

### Changed
- Version is single-sourced from `fakturownia_client.__version__`.
- License metadata migrated to PEP 639.

## [0.0.1] - 2026-07-28

### Added
- Initial release: sync (`FakturowniaClient`) and async
  (`AsyncFakturowniaClient`) clients for invoices, clients and products;
  Bearer-header-only authentication; pydantic v2 models; typed exceptions;
  auto-pagination.
