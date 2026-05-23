"""End-to-end test of the upload-workbook CLI command via respx."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
import respx
from typer.testing import CliRunner

from peerbench.cli import app

SUPABASE_URL = "https://abc.supabase.co"
BUCKET = "peerbench-exports"


@pytest.mark.integration
@respx.mock
def test_upload_workbook_happy_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPABASE_URL", SUPABASE_URL)
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "key")
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql://user:pass@localhost/db"
    )  # required by pydantic-settings
    monkeypatch.setenv("FDIC_API_KEY", "unused")  # required by pydantic-settings

    xlsx_route = respx.put(f"{SUPABASE_URL}/storage/v1/object/{BUCKET}/latest.xlsx").mock(
        return_value=httpx.Response(200)
    )
    json_route = respx.put(f"{SUPABASE_URL}/storage/v1/object/{BUCKET}/latest.json").mock(
        return_value=httpx.Response(200)
    )

    wb = tmp_path / "peerbench_4063_2025-Q4.xlsx"
    wb.write_bytes(b"PK\x03\x04" + b"\x00" * 100)

    runner = CliRunner()
    result = runner.invoke(app, ["upload-workbook", "--file", str(wb)])

    assert result.exit_code == 0, result.stdout
    assert xlsx_route.called
    assert json_route.called

    # Order matters: xlsx first, then json (so manifest never points at missing file).
    all_calls = list(respx.calls)
    first_path = all_calls[0].request.url.path
    second_path = all_calls[1].request.url.path
    assert first_path.endswith("/latest.xlsx")
    assert second_path.endswith("/latest.json")
