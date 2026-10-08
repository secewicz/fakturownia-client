import json

import httpx
import pytest
import respx

from fakturownia_client import (
    ApiRecord,
    AsyncFakturowniaClient,
    Invoice,
    NotFoundError,
)
from tests.conftest import TOKEN


@pytest.fixture
async def aclient(api: respx.MockRouter) -> AsyncFakturowniaClient:
    async with AsyncFakturowniaClient("testfirma", TOKEN, max_retries=0) as fk:
        yield fk


async def test_async_list_invoices_uses_bearer_header(
    api: respx.MockRouter, aclient: AsyncFakturowniaClient
) -> None:
    route = api.get("/invoices.json").mock(
        return_value=httpx.Response(200, json=[{"id": 1, "number": "A/1"}])
    )

    invoices = await aclient.list_invoices(period="this_month")

    assert isinstance(invoices[0], Invoice)
    request = route.calls.last.request
    assert request.headers["Authorization"] == f"Bearer {TOKEN}"
    assert "api_token" not in str(request.url)


async def test_async_create_invoice_wraps_payload(
    api: respx.MockRouter, aclient: AsyncFakturowniaClient
) -> None:
    route = api.post("/invoices.json").mock(return_value=httpx.Response(201, json={"id": 2}))

    created = await aclient.create_invoice({"buyer_name": "ACME"})

    assert created.id == 2
    assert json.loads(route.calls.last.request.content) == {"invoice": {"buyer_name": "ACME"}}


async def test_async_iter_invoices_paginates(
    api: respx.MockRouter, aclient: AsyncFakturowniaClient
) -> None:
    route = api.get("/invoices.json").mock(
        side_effect=[
            httpx.Response(200, json=[{"id": i} for i in range(100)]),
            httpx.Response(200, json=[{"id": 100}]),
        ]
    )

    invoices = [inv async for inv in aclient.iter_invoices()]

    assert len(invoices) == 101
    assert route.call_count == 2


async def test_async_payments_roundtrip(
    api: respx.MockRouter, aclient: AsyncFakturowniaClient
) -> None:
    payment_json = {"id": 77, "name": "Payment 001", "price": "100.0", "paid": True}
    api.get("/banking/payments.json").mock(return_value=httpx.Response(200, json=[payment_json]))
    api.get("/banking/payments/77.json").mock(return_value=httpx.Response(200, json=payment_json))
    create = api.post("/banking/payments.json").mock(
        return_value=httpx.Response(201, json=payment_json)
    )
    update = api.patch("/banking/payments/77.json").mock(
        return_value=httpx.Response(200, json=payment_json)
    )
    delete = api.delete("/banking/payments/77.json").mock(return_value=httpx.Response(200))

    assert (await aclient.list_payments())[0].id == 77
    assert (await aclient.get_payment(77)).name == "Payment 001"
    await aclient.create_payment({"name": "Payment 001", "price": 100.0, "invoice_id": 555})
    await aclient.update_payment(77, {"paid": False})
    await aclient.delete_payment(77)

    assert json.loads(create.calls.last.request.content) == {
        "banking_payment": {"name": "Payment 001", "price": 100.0, "invoice_id": 555}
    }
    assert json.loads(update.calls.last.request.content) == {"banking_payment": {"paid": False}}
    assert delete.called


async def test_async_iter_payments_paginates(
    api: respx.MockRouter, aclient: AsyncFakturowniaClient
) -> None:
    api.get("/banking/payments.json").mock(
        side_effect=[
            httpx.Response(200, json=[{"id": i} for i in range(100)]),
            httpx.Response(200, json=[{"id": 100}]),
        ]
    )

    assert len([p async for p in aclient.iter_payments()]) == 101


async def test_async_send_invoice_by_email(
    api: respx.MockRouter, aclient: AsyncFakturowniaClient
) -> None:
    route = api.post("/invoices/1/send_by_email.json").mock(
        return_value=httpx.Response(200, json={"code": "success"})
    )

    await aclient.send_invoice_by_email(1, email_to="a@acme.pl")

    assert dict(httpx.URL(str(route.calls.last.request.url)).params)["email_to"] == "a@acme.pl"


async def test_async_read_only_resources_mirror_sync_client(
    api: respx.MockRouter, aclient: AsyncFakturowniaClient
) -> None:
    resources = [
        ("recurrings", "recurring"),
        ("price_lists", "price_list"),
        ("warehouses", "warehouse"),
        ("warehouse_documents", "warehouse_document"),
        ("categories", "category"),
        ("departments", "department"),
        ("issuers", "issuer"),
        ("bank_accounts", "bank_account"),
        ("webhooks", "webhook"),
    ]
    for plural, singular in resources:
        api.get(f"/{plural}.json").mock(return_value=httpx.Response(200, json=[{"id": 1}]))
        api.get(f"/{plural}/1.json").mock(return_value=httpx.Response(200, json={"id": 1}))

        listed = await getattr(aclient, f"list_{plural}")(page=2, per_page=10)
        fetched = await getattr(aclient, f"get_{singular}")(1)

        assert isinstance(listed[0], ApiRecord)
        assert fetched.id == 1

    route = api.get("/warehouse_actions.json").mock(
        return_value=httpx.Response(200, json=[{"id": 2, "kind": "transfer"}])
    )
    actions = await aclient.list_warehouse_actions(warehouse_id=4, kind="transfer")
    assert actions[0].kind == "transfer"
    assert dict(httpx.URL(str(route.calls.last.request.url)).params)["warehouse_id"] == "4"


async def test_async_error_mapping(api: respx.MockRouter, aclient: AsyncFakturowniaClient) -> None:
    api.get("/invoices/1.json").mock(
        return_value=httpx.Response(404, json={"code": "error", "message": "nope"})
    )

    with pytest.raises(NotFoundError):
        await aclient.get_invoice(1)


async def test_async_pdf_bytes(api: respx.MockRouter, aclient: AsyncFakturowniaClient) -> None:
    api.get("/invoices/1.pdf").mock(return_value=httpx.Response(200, content=b"%PDF"))

    assert await aclient.download_invoice_pdf(1) == b"%PDF"
