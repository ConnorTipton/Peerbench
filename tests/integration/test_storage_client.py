"""Integration tests for SupabaseStorageClient via respx (mocked transport)."""

from __future__ import annotations

import httpx
import pytest
import respx

from peerbench.storage.client import SupabaseStorageClient

URL = "https://abc.supabase.co"
KEY = "service-role-key"
BUCKET = "peerbench-exports"
XLSX_CT = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@pytest.fixture
def client() -> SupabaseStorageClient:
    return SupabaseStorageClient(url=URL, service_role_key=KEY)


@respx.mock
def test_upload_xlsx_success(client: SupabaseStorageClient) -> None:
    route = respx.put(f"{URL}/storage/v1/object/{BUCKET}/latest.xlsx").mock(
        return_value=httpx.Response(200, json={"Key": f"{BUCKET}/latest.xlsx"})
    )
    client.upload(BUCKET, "latest.xlsx", b"PKxx", XLSX_CT)
    assert route.called
    req = route.calls.last.request
    assert req.headers["authorization"] == f"Bearer {KEY}"
    assert req.headers["apikey"] == KEY
    assert req.headers["x-upsert"] == "true"
    assert req.headers["content-type"] == XLSX_CT
    assert req.content == b"PKxx"


@respx.mock
def test_upload_json_success(client: SupabaseStorageClient) -> None:
    route = respx.put(f"{URL}/storage/v1/object/{BUCKET}/latest.json").mock(
        return_value=httpx.Response(200, json={"Key": f"{BUCKET}/latest.json"})
    )
    client.upload(BUCKET, "latest.json", b'{"a":1}', "application/json")
    req = route.calls.last.request
    assert req.headers["content-type"] == "application/json"


@respx.mock
def test_upload_raises_on_4xx(client: SupabaseStorageClient) -> None:
    respx.put(f"{URL}/storage/v1/object/{BUCKET}/latest.xlsx").mock(
        return_value=httpx.Response(401, text='{"error":"unauthorized"}')
    )
    with pytest.raises(RuntimeError, match="401"):
        client.upload(BUCKET, "latest.xlsx", b"x", XLSX_CT)


@respx.mock
def test_upload_raises_on_5xx(client: SupabaseStorageClient) -> None:
    respx.put(f"{URL}/storage/v1/object/{BUCKET}/latest.xlsx").mock(
        return_value=httpx.Response(503, text="upstream timeout")
    )
    with pytest.raises(RuntimeError, match="503"):
        client.upload(BUCKET, "latest.xlsx", b"x", XLSX_CT)


@respx.mock
def test_upload_propagates_network_error(client: SupabaseStorageClient) -> None:
    respx.put(f"{URL}/storage/v1/object/{BUCKET}/latest.xlsx").mock(
        side_effect=httpx.ConnectError("connection refused")
    )
    with pytest.raises(httpx.ConnectError):
        client.upload(BUCKET, "latest.xlsx", b"x", XLSX_CT)


@respx.mock
def test_upload_strips_trailing_slash_on_url() -> None:
    client = SupabaseStorageClient(url=f"{URL}/", service_role_key=KEY)
    route = respx.put(f"{URL}/storage/v1/object/{BUCKET}/latest.xlsx").mock(
        return_value=httpx.Response(200)
    )
    client.upload(BUCKET, "latest.xlsx", b"x", XLSX_CT)
    assert route.called
