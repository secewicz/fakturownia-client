import httpx
import pytest
import respx

from fakturownia_client import FakturowniaClient
from fakturownia_client.models import ApiRecord

RESOURCE_CASES = [
    ("recurrings", "recurring", "/recurrings.json", "/recurrings/11.json"),
    ("price_lists", "price_list", "/price_lists.json", "/price_lists/11.json"),
    ("warehouses", "warehouse", "/warehouses.json", "/warehouses/11.json"),
    (
        "warehouse_documents",
        "warehouse_document",
        "/warehouse_documents.json",
        "/warehouse_documents/11.json",
    ),
    ("categories", "category", "/categories.json", "/categories/11.json"),
    ("departments", "department", "/departments.json", "/departments/11.json"),
    ("issuers", "issuer", "/issuers.json", "/issuers/11.json"),
    ("bank_accounts", "bank_account", "/bank_accounts.json", "/bank_accounts/11.json"),
    ("webhooks", "webhook", "/webhooks.json", "/webhooks/11.json"),
]


@pytest.mark.parametrize(("resource", "singular", "list_path", "get_path"), RESOURCE_CASES)
def test_sync_list_and_get_read_only_resources(
    api: respx.MockRouter,
    client: FakturowniaClient,
    resource: str,
    singular: str,
    list_path: str,
    get_path: str,
) -> None:
    record = {"id": 11, "name": f"Example {resource}", "custom_field": "preserved"}
    list_route = api.get(list_path).mock(return_value=httpx.Response(200, json=[record]))
    api.get(get_path).mock(return_value=httpx.Response(200, json=record))

    listed = getattr(client, f"list_{resource}")(page=2, per_page=50)
    fetched = getattr(client, f"get_{singular}")(11)

    assert isinstance(listed[0], ApiRecord)
    assert listed[0].id == 11
    assert listed[0].name == f"Example {resource}"
    assert listed[0].custom_field == "preserved"
    assert fetched.id == 11
    params = dict(httpx.URL(str(list_route.calls.last.request.url)).params)
    assert params == {"page": "2", "per_page": "50"}


def test_list_warehouse_actions_forwards_document_filters(
    api: respx.MockRouter, client: FakturowniaClient
) -> None:
    route = api.get("/warehouse_actions.json").mock(
        return_value=httpx.Response(200, json=[{"id": 31, "kind": "income", "product_id": 9}])
    )

    actions = client.list_warehouse_actions(
        warehouse_id=4,
        kind="income",
        product_id=9,
        date_from="2026-09-01",
        date_to="2026-09-30",
        from_warehouse_document=10,
        to_warehouse_document=20,
        warehouse_document_id=15,
        page=3,
        per_page=100,
    )

    assert actions[0].id == 31
    assert actions[0].kind == "income"
    assert dict(httpx.URL(str(route.calls.last.request.url)).params) == {
        "warehouse_id": "4",
        "kind": "income",
        "product_id": "9",
        "date_from": "2026-09-01",
        "date_to": "2026-09-30",
        "from_warehouse_document": "10",
        "to_warehouse_document": "20",
        "warehouse_document_id": "15",
        "page": "3",
        "per_page": "100",
    }
