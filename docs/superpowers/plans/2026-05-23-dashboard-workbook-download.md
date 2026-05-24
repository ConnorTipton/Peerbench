# Dashboard Workbook Download Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface the Phase 4.2 Excel comp workbook on the dashboard so users can download it without going to GitHub.

**Architecture:** The daily-ingest GitHub Action grows two new steps — generate the workbook + upload to a public Supabase Storage bucket alongside a small JSON manifest. The dashboard fetches the manifest server-side, renders a download link with a freshness subtitle when present, and renders nothing when absent. Zero new Python deps (uses existing `httpx`); zero new web deps; zero new Vercel runtime.

**Tech Stack:**
- Python 3.13, `httpx`, `respx`, `typer`, `openpyxl` (all existing)
- Next.js 16 App Router, server components, vitest (all existing)
- Supabase Storage REST API (PUT against public bucket)
- GitHub Actions (extend existing `daily-ingest.yml`)

**Spec:** `docs/superpowers/specs/2026-05-23-dashboard-workbook-download-design.md`

---

## File map

**New Python files:**
- `src/peerbench/storage/__init__.py` — re-exports
- `src/peerbench/storage/manifest.py` — pure manifest payload builder
- `src/peerbench/storage/client.py` — httpx wrapper for Supabase Storage REST
- `tests/unit/test_storage_manifest.py` — pure-function tests
- `tests/integration/test_storage_client.py` — respx-mocked HTTP tests
- `tests/integration/test_cli_upload_workbook.py` — CLI happy-path

**Modified Python files:**
- `src/peerbench/cli.py` — add `upload-workbook` command + `--quarter latest` sentinel on `export`

**New web files:**
- `web/lib/workbook-manifest.ts` — server-only fetcher + parser
- `web/lib/workbook-manifest.test.ts` — vitest, mocks `global.fetch`
- `web/components/workbook-download.tsx` — server component

**Modified web files:**
- `web/lib/format.ts` — add `formatRelativeDate`
- `web/lib/format.test.ts` — extend with 5 cases for the new helper
- `web/app/page.tsx` — wire `<WorkbookDownload />` into the header subtitle row

**Modified workflow:**
- `.github/workflows/daily-ingest.yml` — 2 appended steps

**Manual prereq (Task 6):** Create `peerbench-exports` Supabase Storage bucket.

---

## Sprint A — Python pipeline (5 tasks)

### Task 1: `peerbench.storage.manifest` pure builder

**Files:**
- Create: `src/peerbench/storage/__init__.py`
- Create: `src/peerbench/storage/manifest.py`
- Test: `tests/unit/test_storage_manifest.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_storage_manifest.py`:

```python
"""Unit tests for peerbench.storage.manifest — pure-function payload builder."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from peerbench.storage.manifest import build_manifest


@pytest.fixture
def workbook_file(tmp_path: Path) -> Path:
    p = tmp_path / "peerbench_4063_2025-Q4.xlsx"
    p.write_bytes(b"x" * 1234)
    return p


def test_manifest_shape_from_real_file(workbook_file: Path) -> None:
    m = build_manifest(
        workbook_file,
        anchor_cert=4063,
        quarter_id="2025-Q4",
        public_url_base="https://abc.supabase.co/storage/v1/object/public/peerbench-exports",
    )
    assert set(m.keys()) == {"url", "generated_at", "quarter_id", "anchor_cert", "size_bytes"}
    assert m["url"] == "https://abc.supabase.co/storage/v1/object/public/peerbench-exports/latest.xlsx"
    assert m["quarter_id"] == "2025-Q4"
    assert m["anchor_cert"] == 4063


def test_manifest_size_matches_stat(workbook_file: Path) -> None:
    m = build_manifest(
        workbook_file,
        anchor_cert=4063,
        quarter_id="2025-Q4",
        public_url_base="https://x/peerbench-exports",
    )
    assert m["size_bytes"] == 1234


def test_manifest_generated_at_is_iso_utc(workbook_file: Path) -> None:
    m = build_manifest(
        workbook_file,
        anchor_cert=4063,
        quarter_id="2025-Q4",
        public_url_base="https://x/peerbench-exports",
    )
    parsed = datetime.fromisoformat(m["generated_at"])
    assert parsed.tzinfo is not None  # must be timezone-aware
    assert m["generated_at"].endswith("+00:00") or m["generated_at"].endswith("Z")


def test_manifest_strips_trailing_slash_on_url_base(workbook_file: Path) -> None:
    m = build_manifest(
        workbook_file,
        anchor_cert=4063,
        quarter_id="2025-Q4",
        public_url_base="https://abc.supabase.co/storage/v1/object/public/peerbench-exports/",
    )
    assert m["url"] == "https://abc.supabase.co/storage/v1/object/public/peerbench-exports/latest.xlsx"


def test_manifest_passes_through_anchor_and_quarter(workbook_file: Path) -> None:
    m = build_manifest(
        workbook_file,
        anchor_cert=5510,
        quarter_id="2024-Q1",
        public_url_base="https://x/peerbench-exports",
    )
    assert m["anchor_cert"] == 5510
    assert m["quarter_id"] == "2024-Q1"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_storage_manifest.py -v`
Expected: `ModuleNotFoundError: No module named 'peerbench.storage'`

- [ ] **Step 3: Create the package skeleton**

Create `src/peerbench/storage/__init__.py`:

```python
"""Supabase Storage uploader for the Phase 4.2 workbook download path."""

from peerbench.storage.client import SupabaseStorageClient
from peerbench.storage.manifest import build_manifest

__all__ = ["SupabaseStorageClient", "build_manifest"]
```

- [ ] **Step 4: Implement the manifest builder**

Create `src/peerbench/storage/manifest.py`:

```python
"""Pure-function payload builder for the workbook manifest JSON."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def build_manifest(
    workbook_path: Path,
    *,
    anchor_cert: int,
    quarter_id: str,
    public_url_base: str,
) -> dict[str, Any]:
    """Build the manifest JSON dict for the dashboard to consume.

    The dashboard reads `latest.json` from the same Supabase Storage bucket
    that holds `latest.xlsx`; this builder is the single source of truth for
    the manifest shape.
    """
    base = public_url_base.rstrip("/")
    return {
        "url": f"{base}/latest.xlsx",
        "generated_at": datetime.now(UTC).isoformat(),
        "quarter_id": quarter_id,
        "anchor_cert": anchor_cert,
        "size_bytes": workbook_path.stat().st_size,
    }
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_storage_manifest.py -v`
Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add src/peerbench/storage/__init__.py src/peerbench/storage/manifest.py tests/unit/test_storage_manifest.py
git commit -m "feat(storage): manifest payload builder"
```

---

### Task 2: `peerbench.storage.client` httpx wrapper

**Files:**
- Create: `src/peerbench/storage/client.py`
- Test: `tests/integration/test_storage_client.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/integration/test_storage_client.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/integration/test_storage_client.py -v`
Expected: `ImportError: cannot import name 'SupabaseStorageClient' from 'peerbench.storage.client'`

- [ ] **Step 3: Implement the client**

Create `src/peerbench/storage/client.py`:

```python
"""Thin httpx wrapper around the Supabase Storage REST API."""

from __future__ import annotations

import httpx


class SupabaseStorageClient:
    """Single-purpose client: upload a file to a public Supabase Storage bucket.

    We use httpx directly (already a project dep) instead of supabase-py to
    avoid pulling in 5 transitive deps for one PUT call per day.
    """

    def __init__(self, *, url: str, service_role_key: str) -> None:
        self._url = url.rstrip("/")
        self._key = service_role_key

    def upload(self, bucket: str, path: str, body: bytes, content_type: str) -> None:
        """PUT `body` to `<bucket>/<path>` with upsert semantics.

        Raises RuntimeError on non-2xx (with response body in the message).
        Propagates httpx network errors (ConnectError, TimeoutException) to
        the caller — the daily cron treats both as "fail loud, retry tomorrow."
        """
        endpoint = f"{self._url}/storage/v1/object/{bucket}/{path}"
        headers = {
            "Authorization": f"Bearer {self._key}",
            "apikey": self._key,
            "x-upsert": "true",
            "Content-Type": content_type,
        }
        with httpx.Client(timeout=30.0) as http:
            resp = http.put(endpoint, content=body, headers=headers)
        if resp.status_code >= 300:
            raise RuntimeError(
                f"Supabase Storage upload failed: {resp.status_code} {resp.text}"
            )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/integration/test_storage_client.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add src/peerbench/storage/client.py tests/integration/test_storage_client.py
git commit -m "feat(storage): SupabaseStorageClient httpx wrapper"
```

---

### Task 3: `peerbench export --quarter latest` sentinel

**Files:**
- Modify: `src/peerbench/cli.py` (the existing `export_cmd` at lines ~386-421)
- Test: `tests/integration/test_cli_export_latest.py` (integration because it hits the live DB)

- [ ] **Step 1: Write the failing test**

Create `tests/integration/test_cli_export_latest.py`:

```python
"""Verify the `peerbench export --quarter latest` sentinel resolves to MAX(quarter_id)."""

from __future__ import annotations

from peerbench.db import Quarter, get_session


def test_resolve_latest_quarter_id() -> None:
    """Importable helper resolves to the most recent quarter_id in the DB."""
    from peerbench.cli import _resolve_latest_quarter_id

    with get_session() as session:
        latest = _resolve_latest_quarter_id(session)
        max_in_db = max(q.quarter_id for q in session.query(Quarter).all())
        assert latest == max_in_db
```

Note: this is an integration test against the live DB. Add `@pytest.mark.integration` if the project's existing integration tests use that marker (check one of `tests/integration/test_*.py` for the pattern).

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/integration/test_cli_export_latest.py -v`
Expected: `ImportError: cannot import name '_resolve_latest_quarter_id' from 'peerbench.cli'`

- [ ] **Step 3: Add the helper and sentinel branch**

In `src/peerbench/cli.py`, add to the existing imports at the top of the file:

```python
from sqlalchemy import func
from sqlalchemy.orm import Session
```

(`select` is already imported; `func` may or may not be — add it if missing.)

Then, above the existing `export_cmd` function (around line 386), add:

```python
def _resolve_latest_quarter_id(session: Session) -> str:
    """Return MAX(quarters.quarter_id). Raises ValueError if the table is empty."""
    latest = session.scalar(select(func.max(Quarter.quarter_id)))
    if latest is None:
        raise ValueError("no quarters in DB — run `peerbench ingest` first")
    return latest
```

Then modify `export_cmd` to handle the sentinel. Find:

```python
    with get_session() as session:
        try:
            out_path = run_export(
                session,
                anchor_cert=anchor,
                quarter_id=quarter,
                out_dir=output,
            )
```

Replace with:

```python
    with get_session() as session:
        try:
            resolved_quarter = (
                _resolve_latest_quarter_id(session) if quarter == "latest" else quarter
            )
            out_path = run_export(
                session,
                anchor_cert=anchor,
                quarter_id=resolved_quarter,
                out_dir=output,
            )
```

Also update the docstring of the option:

```python
    quarter: Annotated[
        str,
        typer.Option("--quarter", help="Quarter ID 'YYYY-Qn' (e.g. 2025-Q4) or 'latest'"),
    ],
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_cli_export_latest.py -v`
Expected: 1 passed.

Also smoke-test the CLI directly:

```bash
uv run peerbench export --quarter latest --output ./output --anchor 4063
ls -la ./output/peerbench_4063_*.xlsx
```

Expected: workbook file matching the most recent quarter in your DB.

- [ ] **Step 5: Commit**

```bash
git add src/peerbench/cli.py tests/unit/test_cli_export_latest.py
git commit -m "feat(cli): peerbench export --quarter latest sentinel"
```

---

### Task 4: `peerbench upload-workbook` CLI command

**Files:**
- Modify: `src/peerbench/cli.py` (add new `upload_workbook_cmd`)
- Test: `tests/integration/test_cli_upload_workbook.py`

- [ ] **Step 1: Write the failing test**

Create `tests/integration/test_cli_upload_workbook.py`:

```python
"""End-to-end test of the upload-workbook CLI command via respx."""

from __future__ import annotations

from pathlib import Path

import httpx
import respx
from typer.testing import CliRunner

from peerbench.cli import app

SUPABASE_URL = "https://abc.supabase.co"
BUCKET = "peerbench-exports"


@respx.mock
def test_upload_workbook_happy_path(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SUPABASE_URL", SUPABASE_URL)
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "key")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")  # unused but pydantic-settings requires it
    monkeypatch.setenv("FDIC_API_KEY", "unused")  # ditto

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
    # respx records calls globally on the mock router.
    all_calls = list(respx.calls)
    first_path = all_calls[0].request.url.path
    second_path = all_calls[1].request.url.path
    assert first_path.endswith("/latest.xlsx")
    assert second_path.endswith("/latest.json")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/integration/test_cli_upload_workbook.py -v`
Expected: `typer error: no such command 'upload-workbook'`

- [ ] **Step 3: Implement the CLI command**

In `src/peerbench/cli.py`, after the existing `export_cmd` and before `export_field_deps`, add:

```python
@app.command("upload-workbook")
def upload_workbook_cmd(
    file: Annotated[
        Path,
        typer.Option("--file", help="Path to the .xlsx file emitted by `peerbench export`"),
    ],
    anchor: Annotated[
        int,
        typer.Option("--anchor", help="FDIC certificate number"),
    ] = 4063,
    bucket: Annotated[
        str,
        typer.Option("--bucket", help="Supabase Storage bucket name"),
    ] = "peerbench-exports",
) -> None:
    """Upload the workbook + manifest to Supabase Storage.

    The dashboard reads `latest.json` from the same bucket; we PUT the xlsx
    first and the manifest second so the manifest never points at a file
    that hasn't been uploaded yet.
    """
    import json
    import re

    from peerbench.storage import SupabaseStorageClient, build_manifest

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )

    if not file.exists():
        typer.echo(f"workbook not found: {file}", err=True)
        raise typer.Exit(code=2)

    # Parse quarter_id from filename: peerbench_<cert>_<quarter>.xlsx
    match = re.match(r"peerbench_\d+_(\d{4}-Q[1-4])\.xlsx$", file.name)
    if not match:
        typer.echo(
            f"filename {file.name!r} does not match peerbench_<cert>_<quarter>.xlsx",
            err=True,
        )
        raise typer.Exit(code=2)
    quarter_id = match.group(1)

    settings = get_settings()
    public_url_base = (
        f"{settings.supabase_url.rstrip('/')}/storage/v1/object/public/{bucket}"
    )

    client = SupabaseStorageClient(
        url=settings.supabase_url,
        service_role_key=settings.supabase_service_role_key,
    )

    manifest = build_manifest(
        file,
        anchor_cert=anchor,
        quarter_id=quarter_id,
        public_url_base=public_url_base,
    )

    XLSX_CT = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    client.upload(bucket, "latest.xlsx", file.read_bytes(), XLSX_CT)
    client.upload(
        bucket, "latest.json", json.dumps(manifest, indent=2).encode("utf-8"), "application/json"
    )
    typer.echo(f"uploaded {file.name} → {public_url_base}/latest.xlsx")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/integration/test_cli_upload_workbook.py -v`
Expected: 1 passed.

- [ ] **Step 5: Run the full Python test suite to verify no regressions**

Run: `uv run pytest -q`
Expected: 85 (existing) + 13 (new: 5 manifest + 6 client + 1 latest-quarter + 1 upload-CLI) = 98 passed.

- [ ] **Step 6: Type-check the new package**

Run: `uv run pyright src/peerbench/storage/ src/peerbench/cli.py`
Expected: 0 errors.

- [ ] **Step 7: Commit**

```bash
git add src/peerbench/cli.py tests/integration/test_cli_upload_workbook.py
git commit -m "feat(cli): peerbench upload-workbook command"
```

---

### Task 5: Manual smoke test of the Python pipeline end-to-end

**Files:** none — manual verification.

- [ ] **Step 1: Run the export against the real DB**

```bash
uv run peerbench export --quarter latest --output ./output --anchor 4063
ls -la ./output/peerbench_4063_*.xlsx
```

Expected: a workbook file matching the most recent quarter in your DB.

- [ ] **Step 2: Confirm Supabase env vars are set locally**

Run: `cat .env | grep -E "^(SUPABASE_URL|SUPABASE_SERVICE_ROLE_KEY)"`
Expected: both variables present and non-empty.

- [ ] **Step 3: STOP — bucket doesn't exist yet**

Defer the live upload smoke test to Task 6 after the bucket is created. Move on to Task 6.

---

## Sprint B — GitHub Action (2 tasks)

### Task 6: Create the `peerbench-exports` Supabase Storage bucket (MANUAL)

**Files:** none — manual operation in Supabase dashboard.

- [ ] **Step 1: Create the bucket**

1. Open https://supabase.com/dashboard/project/<your-project>/storage/buckets
2. Click "New bucket"
3. Name: `peerbench-exports`
4. Public bucket: **checked**
5. File size limit: 5 MB (workbooks are ~60 KB; this is conservative)
6. Allowed MIME types: leave empty (any)
7. Click "Create bucket"

- [ ] **Step 2: Verify the bucket exists and is public**

Run: `curl -I https://<project>.supabase.co/storage/v1/object/public/peerbench-exports/missing.xlsx`
Expected: `HTTP/2 400` (bucket exists, file does not) — NOT `404` (bucket does not exist).

If you get a connection error or unexpected status, fix the bucket setup before continuing.

- [ ] **Step 3: Do a one-shot manual upload to verify creds end-to-end**

```bash
uv run peerbench upload-workbook --file ./output/peerbench_4063_2025-Q4.xlsx
```

(Use the actual filename from Task 5 Step 1.)

Expected: stdout `uploaded peerbench_4063_<quarter>.xlsx → https://.../latest.xlsx`.

- [ ] **Step 4: Confirm both objects landed**

Run:
```bash
curl -I https://<project>.supabase.co/storage/v1/object/public/peerbench-exports/latest.xlsx
curl -s https://<project>.supabase.co/storage/v1/object/public/peerbench-exports/latest.json
```

Expected:
- `latest.xlsx`: `HTTP/2 200`, `content-length` matching the local file.
- `latest.json`: a JSON body with `url`, `generated_at`, `quarter_id`, `anchor_cert`, `size_bytes`.

- [ ] **Step 5: No commit — this is a manual prereq.**

---

### Task 7: Append export + upload steps to `daily-ingest.yml`

**Files:**
- Modify: `.github/workflows/daily-ingest.yml`

- [ ] **Step 1: Add the two steps**

In `.github/workflows/daily-ingest.yml`, find the last existing step (the `Heartbeat` step around line 57):

```yaml
      - name: Heartbeat
        run: echo "Heartbeat $(date -u +%Y-%m-%dT%H:%M:%SZ)"
```

Insert two new steps BEFORE it (so a workbook failure still leaves a heartbeat-on-success signal — actually, see Step 2 design call below):

```yaml
      - name: Generate workbook
        run: uv run peerbench export --quarter latest --output ./output

      - name: Upload workbook to Supabase Storage
        run: |
          workbook=$(ls ./output/peerbench_*.xlsx | head -1)
          uv run peerbench upload-workbook --file "$workbook"

      - name: Heartbeat
        run: echo "Heartbeat $(date -u +%Y-%m-%dT%H:%M:%SZ)"
```

Note on ordering: the heartbeat stays last. If export/upload fails, the heartbeat step won't run (GitHub Actions defaults to fail-fast within a job). That's the desired behavior — the Action firing is the heartbeat signal, and a red firing is a true alert. The workflow comment at the top of the file already states "doubles as the Supabase free-tier inactivity heartbeat" — that contract is preserved because Supabase counts the ingest writes, not the workflow step.

- [ ] **Step 2: Verify the YAML parses**

Run: `uv run python -c "import yaml; yaml.safe_load(open('.github/workflows/daily-ingest.yml'))"`
Expected: no exception.

- [ ] **Step 3: Commit and push**

```bash
git add .github/workflows/daily-ingest.yml
git commit -m "ci(daily-ingest): generate + upload workbook to Supabase Storage"
```

(Don't push yet — wait until the dashboard side is also ready so a single PR ships the full feature.)

- [ ] **Step 4: Manual workflow trigger after merge**

After the PR merges, manually trigger the workflow once to confirm production behavior:

```bash
gh workflow run daily-ingest.yml --ref main
gh run watch
```

Expected: workflow completes green; new `latest.xlsx` / `latest.json` timestamps in the bucket.

---

## Sprint C — Dashboard (4 tasks)

### Task 8: `formatRelativeDate` helper in `web/lib/format.ts`

**Files:**
- Modify: `web/lib/format.ts` (append the new helper)
- Modify: `web/lib/format.test.ts` (append 5 cases)

- [ ] **Step 1: Write the failing tests**

In `web/lib/format.test.ts`, append:

```ts
import { describe, expect, it, vi } from "vitest";
import { formatRelativeDate } from "./format";

describe("formatRelativeDate", () => {
  const NOW = new Date("2026-05-23T12:00:00Z");

  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(NOW);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("returns 'today' for a timestamp within the last 24h", () => {
    expect(formatRelativeDate("2026-05-23T03:00:00Z")).toBe("today");
  });

  it("returns 'yesterday' for a timestamp 24–48h old", () => {
    expect(formatRelativeDate("2026-05-22T08:00:00Z")).toBe("yesterday");
  });

  it("returns 'N days ago' for 2–7 days old", () => {
    expect(formatRelativeDate("2026-05-20T12:00:00Z")).toBe("3 days ago");
  });

  it("returns an absolute date for >7 days old", () => {
    expect(formatRelativeDate("2026-05-10T12:00:00Z")).toBe("on May 10, 2026");
  });

  it("returns 'today' for a future timestamp (clock skew)", () => {
    expect(formatRelativeDate("2026-05-24T12:00:00Z")).toBe("today");
  });
});
```

Note: ensure `beforeEach` / `afterEach` are imported from vitest at the top of the file. If the existing tests don't use fake timers, add `import { beforeEach, afterEach } from "vitest";` to the imports.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd web && npm test -- format.test.ts`
Expected: 5 new failures with `formatRelativeDate is not a function` (or similar).

- [ ] **Step 3: Implement the helper**

In `web/lib/format.ts`, append:

```ts
/**
 * Render an ISO-8601 timestamp as a human-relative phrase for the workbook
 * download freshness subtitle. Future timestamps (clock skew) clamp to "today".
 */
export function formatRelativeDate(iso: string): string {
  const then = new Date(iso);
  const now = new Date();
  const diffMs = now.getTime() - then.getTime();
  const dayMs = 24 * 60 * 60 * 1000;

  if (diffMs < dayMs) return "today";
  if (diffMs < 2 * dayMs) return "yesterday";
  const days = Math.floor(diffMs / dayMs);
  if (days <= 7) return `${days} days ago`;

  return `on ${then.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}`;
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd web && npm test -- format.test.ts`
Expected: all format tests passing (existing 19 + new 5 = 24).

- [ ] **Step 5: Commit**

```bash
git add web/lib/format.ts web/lib/format.test.ts
git commit -m "feat(web): formatRelativeDate helper for workbook freshness subtitle"
```

---

### Task 9: `workbook-manifest.ts` server-only fetcher

**Files:**
- Create: `web/lib/workbook-manifest.ts`
- Create: `web/lib/workbook-manifest.test.ts`

- [ ] **Step 1: Write the failing tests**

Create `web/lib/workbook-manifest.test.ts`:

```ts
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fetchWorkbookManifest } from "./workbook-manifest";

const MANIFEST_URL = "https://abc.supabase.co/storage/v1/object/public/peerbench-exports/latest.json";

const VALID_MANIFEST = {
  url: "https://abc.supabase.co/storage/v1/object/public/peerbench-exports/latest.xlsx",
  generated_at: "2026-05-23T03:07:42Z",
  quarter_id: "2025-Q4",
  anchor_cert: 4063,
  size_bytes: 62513,
};

describe("fetchWorkbookManifest", () => {
  beforeEach(() => {
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_URL", "https://abc.supabase.co");
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it("returns parsed manifest on 200", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify(VALID_MANIFEST), { status: 200 }),
    );
    const m = await fetchWorkbookManifest();
    expect(m).toEqual({
      url: VALID_MANIFEST.url,
      generatedAt: VALID_MANIFEST.generated_at,
      quarterId: VALID_MANIFEST.quarter_id,
      sizeBytes: VALID_MANIFEST.size_bytes,
    });
  });

  it("returns null on 404", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(new Response("", { status: 404 }));
    expect(await fetchWorkbookManifest()).toBeNull();
  });

  it("returns null on AbortError (timeout)", async () => {
    vi.spyOn(global, "fetch").mockRejectedValue(
      Object.assign(new Error("aborted"), { name: "AbortError" }),
    );
    expect(await fetchWorkbookManifest()).toBeNull();
  });

  it("returns null on network error", async () => {
    vi.spyOn(global, "fetch").mockRejectedValue(new TypeError("fetch failed"));
    expect(await fetchWorkbookManifest()).toBeNull();
  });

  it("returns null on malformed JSON", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    vi.spyOn(global, "fetch").mockResolvedValue(
      new Response("not json", { status: 200 }),
    );
    expect(await fetchWorkbookManifest()).toBeNull();
  });

  it("returns null when required field is missing", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    const { generated_at, ...incomplete } = VALID_MANIFEST;
    vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify(incomplete), { status: 200 }),
    );
    expect(await fetchWorkbookManifest()).toBeNull();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd web && npm test -- workbook-manifest.test.ts`
Expected: 6 failures with module-not-found error.

- [ ] **Step 3: Implement the fetcher**

Create `web/lib/workbook-manifest.ts`:

```ts
/**
 * Server-only fetcher for the daily-uploaded workbook manifest.
 *
 * Reads `latest.json` from the public Supabase Storage bucket. All failure
 * modes (404, timeout, network, malformed JSON, wrong shape) return null so
 * the dashboard renders gracefully on first-run and during outages.
 *
 * The bucket is uploaded to by the daily-ingest GitHub Action.
 */

export type WorkbookManifest = {
  url: string;
  generatedAt: string; // ISO-8601 UTC
  quarterId: string;
  sizeBytes: number;
};

const BUCKET = "peerbench-exports";
const TIMEOUT_MS = 3000;

function manifestUrl(): string {
  const base = process.env.NEXT_PUBLIC_SUPABASE_URL?.replace(/\/$/, "");
  if (!base) throw new Error("NEXT_PUBLIC_SUPABASE_URL is not set");
  return `${base}/storage/v1/object/public/${BUCKET}/latest.json`;
}

function parseManifest(raw: unknown): WorkbookManifest | null {
  if (typeof raw !== "object" || raw === null) return null;
  const r = raw as Record<string, unknown>;
  if (
    typeof r.url !== "string" ||
    typeof r.generated_at !== "string" ||
    typeof r.quarter_id !== "string" ||
    typeof r.size_bytes !== "number"
  ) {
    return null;
  }
  return {
    url: r.url,
    generatedAt: r.generated_at,
    quarterId: r.quarter_id,
    sizeBytes: r.size_bytes,
  };
}

export async function fetchWorkbookManifest(): Promise<WorkbookManifest | null> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const res = await fetch(manifestUrl(), {
      signal: controller.signal,
      next: { revalidate: 300 },
    });
    if (!res.ok) return null;
    let body: unknown;
    try {
      body = await res.json();
    } catch (err) {
      console.error("workbook-manifest: failed to parse JSON", err);
      return null;
    }
    const parsed = parseManifest(body);
    if (!parsed) {
      console.error("workbook-manifest: response did not match expected shape", body);
    }
    return parsed;
  } catch (err) {
    // AbortError, TypeError (network), etc — degrade silently.
    if ((err as Error).name !== "AbortError") {
      // Network errors are noisy in the logs; only surface non-timeout failures.
      console.error("workbook-manifest: fetch failed", err);
    }
    return null;
  } finally {
    clearTimeout(timer);
  }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd web && npm test -- workbook-manifest.test.ts`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add web/lib/workbook-manifest.ts web/lib/workbook-manifest.test.ts
git commit -m "feat(web): workbook-manifest server-only fetcher"
```

---

### Task 10: `WorkbookDownload` server component

**Files:**
- Create: `web/components/workbook-download.tsx`

- [ ] **Step 1: Implement the component**

Create `web/components/workbook-download.tsx`:

```tsx
/**
 * Header download surface for the daily-regenerated Excel comp workbook.
 *
 * Server component — fetches the manifest at request time, returns null when
 * absent (first-run, outage, malformed) so the dashboard degrades to today's
 * behavior. Verified by workbook-manifest.test.ts.
 */

import { formatRelativeDate } from "@/lib/format";
import { fetchWorkbookManifest } from "@/lib/workbook-manifest";

export async function WorkbookDownload() {
  const manifest = await fetchWorkbookManifest();
  if (!manifest) return null;
  return (
    <div className="flex flex-col items-end gap-0.5">
      <a
        href={manifest.url}
        className="text-body text-accent hover:underline"
        download
      >
        Download workbook (.xlsx)
      </a>
      <span className="text-table-data text-text-tertiary">
        Updated {formatRelativeDate(manifest.generatedAt)}
      </span>
    </div>
  );
}
```

- [ ] **Step 2: Verify it type-checks**

Run: `cd web && npx tsc --noEmit`
Expected: 0 errors (1 pre-existing TanStack warning is acceptable).

- [ ] **Step 3: Commit**

```bash
git add web/components/workbook-download.tsx
git commit -m "feat(web): WorkbookDownload server component"
```

---

### Task 11: Wire `<WorkbookDownload />` into `web/app/page.tsx`

**Files:**
- Modify: `web/app/page.tsx` (the right-aligned subtitle slot)

- [ ] **Step 1: Add the import and replace the subtitle slot**

In `web/app/page.tsx`, find:

```tsx
import { AnchorSelect } from "@/components/anchor-select";
import { RatioMatrix } from "@/components/ratio-matrix";
```

Add:

```tsx
import { WorkbookDownload } from "@/components/workbook-download";
```

Then find:

```tsx
      <header className="mb-4 flex items-baseline justify-between gap-4">
        <h1 className="text-page-title font-semibold text-primary">Peerbench</h1>
        <span className="text-body text-text-secondary">
          As of {formatReportDate(data.quarter.report_date)}
        </span>
      </header>
```

Replace with:

```tsx
      <header className="mb-4 flex items-baseline justify-between gap-4">
        <h1 className="text-page-title font-semibold text-primary">Peerbench</h1>
        <div className="flex flex-col items-end gap-1">
          <span className="text-body text-text-secondary">
            As of {formatReportDate(data.quarter.report_date)}
          </span>
          <WorkbookDownload />
        </div>
      </header>
```

- [ ] **Step 2: Verify the dashboard builds and the page renders**

Start the dev server:
```bash
cd web && npm run dev
```

Open http://localhost:3000 — confirm the page loads. With the bucket populated (Task 6), the "Download workbook (.xlsx)" link should appear under "As of …".

If the bucket is empty (e.g. you're testing on a clean Supabase project), the link is absent and the page looks exactly like today. This is the empty-state behavior — not a bug.

- [ ] **Step 3: Smoke-test the click-through**

Click "Download workbook (.xlsx)". Browser should download an `.xlsx` file. Open it — confirm it's the same workbook structure as `uv run peerbench export` produces locally (15 tabs, MidFirst NIM around 2.89%).

- [ ] **Step 4: Run the full vitest suite**

Run: `cd web && npm test`
Expected: 144 (existing) + 11 (new) = 155 passing.

- [ ] **Step 5: Build verification**

Run: `cd web && npm run build`
Expected: clean Turbopack compile + Sentry source-map upload (or skipped if no `SENTRY_AUTH_TOKEN` locally).

- [ ] **Step 6: Commit**

```bash
git add web/app/page.tsx
git commit -m "feat(web): wire WorkbookDownload into dashboard header"
```

---

## Sprint D — Verification + ship (2 tasks)

### Task 12: Sub-agent reviews

**Files:** none — agent invocations.

- [ ] **Step 1: Run the `reviewer` sub-agent**

Use the Task tool to dispatch the `reviewer` sub-agent against the full diff:

```
Subject: Review Peerbench dashboard workbook download PR

Diff: HEAD vs main (compare via `git diff main...HEAD`).

Check specifically:
1. No formula logic in dashboard (web/) or Excel export layer (src/peerbench/export/, src/peerbench/storage/) — both must read from ratios table only.
2. SUPABASE_SERVICE_ROLE_KEY does NOT appear anywhere under web/.
3. Manifest payload shape matches the design spec at docs/superpowers/specs/2026-05-23-dashboard-workbook-download-design.md.
4. New design tokens — there should be NONE. The component must use existing tokens only.
5. Upload order (xlsx before json) is preserved in the CLI command.
6. Empty-state degrades to "looks like today" — no error UI.
```

Expected: PASS, 0 blocking findings. Address any P1/P2 findings before continuing.

- [ ] **Step 2: Run the `design-critic` sub-agent**

Use the Task tool to dispatch `design-critic` against the dashboard diff:

```
Subject: Design review of WorkbookDownload header surface

Diff: web/components/workbook-download.tsx + web/app/page.tsx changes vs main.

Check against docs/design.md:
1. Typography tokens used (text-body, text-table-data, text-text-tertiary).
2. Anchor color for the link feels right vs the existing header chrome.
3. Header layout pressure — does the new component cause the sticky table to lose vertical space?
4. Freshness subtitle tone — banker-appropriate vs too informal?
```

Expected: PASS, 0 blocking. Fix any soft findings worth fixing on-branch.

- [ ] **Step 3: Run `/codex review` as the pre-merge gate**

Standard Sprint 2 / Phase 4.2 pattern — codex round 1 on the full diff.

Expected: GATE PASS, 0 findings. If P2s, fix on-branch and re-run.

- [ ] **Step 4: Commit any review-driven fixes**

If sub-agents or codex surfaced fix-on-branch items:

```bash
git add <files>
git commit -m "fix: <review feedback summary>"
```

---

### Task 13: Ship

**Files:** none — release operations.

- [ ] **Step 1: Push the branch and open the PR**

```bash
git push -u origin <branch-name>
gh pr create --title "Phase 4.2 follow-up: dashboard workbook download" --body "$(cat <<'EOF'
## Summary
- Adds the daily-regenerated Excel workbook as a header download on the dashboard.
- New `peerbench upload-workbook` CLI + `peerbench export --quarter latest` sentinel.
- `daily-ingest.yml` grows two steps: generate workbook → upload to Supabase Storage.
- Dashboard fetches a JSON manifest server-side, hides the link when absent.

## Test plan
- [x] 13 new pytest cases (storage manifest + client + latest-quarter + CLI happy-path) — 85 → 98 total.
- [x] 11 new vitest cases (workbook-manifest fetcher + formatRelativeDate) — 144 → 155 total.
- [x] Manual end-to-end: `uv run peerbench export --quarter latest && uv run peerbench upload-workbook` against prod Supabase succeeded; dashboard renders link + freshness subtitle; click downloads workbook.
- [x] `pyright --strict` clean on src/peerbench/storage/.
- [x] `npm run build` clean.

## Manual prereqs
- `peerbench-exports` bucket created in Supabase Storage (public, 5 MB limit).

## Verification
- Reviewer sub-agent: PASS, 0 blocking.
- Design-critic sub-agent: PASS.
- /codex review: GATE PASS, 0 findings.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 2: Merge after CI is green**

```bash
gh pr merge --squash
```

- [ ] **Step 3: Verify production immediately after deploy**

```bash
curl -s -I https://peerbench-web.vercel.app/ | head -1
```

Expected: `HTTP/2 200`.

Open https://peerbench-web.vercel.app/ in a browser — confirm:
- Page loads.
- "Download workbook (.xlsx)" link appears with "Updated <relative date>" subtitle.
- Clicking downloads a working `.xlsx`.

- [ ] **Step 4: Trigger the workflow once manually to verify the cron path**

```bash
gh workflow run daily-ingest.yml --ref main
gh run watch
```

Expected: workflow goes green; `latest.xlsx` and `latest.json` timestamps in the bucket update.

- [ ] **Step 5: Update `HANDOFF.md`**

Append a post-PR entry describing what landed, mirroring the existing handoff entries' format (TL;DR + diff stats + working-tree state). Add to the top of the file under a new `## TL;DR` line replacement.

- [ ] **Step 6: Commit and push the handoff**

```bash
git add HANDOFF.md
git commit -m "docs(handoff): post-PR-#<n> — dashboard workbook download landed"
git push origin main
```

---

## Definition of done (mirrors spec §DoD)

- [ ] `peerbench-exports` bucket exists in Supabase (manual prereq).
- [ ] `src/peerbench/storage/` package shipped with 11 passing tests (5 manifest + 6 client).
- [ ] `peerbench upload-workbook` CLI works locally against prod Supabase.
- [ ] `peerbench export --quarter latest` resolves to most recent quarter_id.
- [ ] `.github/workflows/daily-ingest.yml` updated; first real firing succeeds.
- [ ] Dashboard at https://peerbench-web.vercel.app/ renders the link with freshness subtitle.
- [ ] Clicking the link downloads the same workbook as local `peerbench export`.
- [ ] Empty-state (no manifest) renders nothing in the download slot.
- [ ] reviewer sub-agent PASS, design-critic sub-agent PASS, /codex review GATE PASS.
- [ ] All tests green; `npm run build` clean; `pyright --strict` clean.
