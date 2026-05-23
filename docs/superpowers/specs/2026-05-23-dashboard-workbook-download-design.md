# Dashboard workbook download — design

**Status:** Draft  
**Date:** 2026-05-23  
**Phase:** 4.2 follow-up (dashboard surface for the Excel comp workbook shipped in PR #19)  
**Author:** Connor + Claude

## Goal

Make the Phase 4.2 Excel comp workbook downloadable directly from the
dashboard at https://peerbench-web.vercel.app/ without sending users to
GitHub.

Three hard constraints from `CLAUDE.md` and the prior session:

1. **No `.xlsx` committed to the repo** — file is regenerated daily; git
   history should stay log-clean.
2. **No Python on Vercel** — the export is a Python pipeline; the
   dashboard runtime is Next.js only.
3. **No formula logic in the dashboard layer** — the dashboard already
   reads `ratios.value` straight from Postgres; the download is just a
   second consumer of the same workbook the export CLI already builds.

## Architecture overview

```
03:00 UTC daily cron (existing daily-ingest.yml)
  → ingest                                (existing step)
  → compute                               (existing step)
  → export workbook   (NEW step)          → output/peerbench_<cert>_<quarter>.xlsx
  → upload workbook   (NEW step)          → Supabase Storage bucket peerbench-exports
                                            • latest.xlsx
                                            • latest.json (manifest)

User loads dashboard
  → page.tsx awaits getMatrixData() AND WorkbookDownload's manifest fetch (parallel)
  → renders matrix + download link with freshness subtitle
  → click → direct browser GET against Supabase CDN, no Vercel hop
```

Three surfaces touched:

| Surface | New files | Modified files |
| :--- | :--- | :--- |
| Python pipeline | `src/peerbench/storage/{__init__,client,manifest}.py` | `src/peerbench/cli.py` (+1 cmd, +1 sentinel) |
| GitHub Action | — | `.github/workflows/daily-ingest.yml` (+2 steps) |
| Dashboard | `web/lib/workbook-manifest.ts`, `web/components/workbook-download.tsx` | `web/app/page.tsx`, `web/lib/format.ts` |

## Design decisions (locked in brainstorm)

| Question | Decision | Rationale |
| :--- | :--- | :--- |
| Upload SDK | **httpx direct REST** | Zero new deps (`httpx` already in `pyproject.toml`). ~50 lines. Supabase-py would add 5 transitive deps for a single PUT call. |
| Bucket access | **Public bucket, stable URL** | Static `<a href>` works during SSR. No service-role key on Vercel (CLAUDE.md forbids it). Data is already-public FDIC data. |
| Link placement | **Right of "As of …", `Download workbook (.xlsx)`** | Slots into existing right-aligned subtitle row. Banker-standard: report date + artifact live together. Single line, no new vertical chrome. |
| Freshness signal | **`Updated <relative date>` subtitle under the link** | Bankers expect freshness on artifacts. Free canary for upload failures — date drifts visibly. |
| Empty-state (pre-first-run) | **Hide link if manifest 404s** | Cleanest. Dashboard looks exactly like today before the first Action firing. |
| Action shape | **Append 2 steps to existing daily-ingest.yml** | Co-locates export with the data refresh that just landed (same `generated_at` truth). Zero new workflows, no inter-workflow coordination, no second `uv sync` cost. Failed ingest → export never runs (correct). |

## Python components

### `src/peerbench/storage/` (new sub-package)

```
src/peerbench/storage/
├── __init__.py          # re-exports upload_workbook, build_manifest
├── client.py            # SupabaseStorageClient: httpx wrapper, ~50 lines
└── manifest.py          # build_manifest(): typed payload builder, ~25 lines
```

**`client.py`** — single class `SupabaseStorageClient(url, service_role_key)`
with one method:

```python
def upload(self, bucket: str, path: str, body: bytes, content_type: str) -> None
```

Wraps `httpx.put(...)` with the Supabase auth headers
(`Authorization: Bearer <key>`, `apikey: <key>`, `x-upsert: true`). Raises
on non-2xx with the response body in the message. Thin enough that
mocking via `respx` (already a test dep) is trivial.

**`manifest.py`** — pure function:

```python
def build_manifest(
    workbook_path: Path,
    *,
    anchor_cert: int,
    quarter_id: str,
    public_url_base: str,  # e.g. https://<project>.supabase.co/storage/v1/object/public/peerbench-exports
) -> dict[str, Any]
```

Reads file size from disk; computes `generated_at` as
`datetime.now(UTC).isoformat()`. No I/O beyond `os.stat`.

**Why two files instead of one** — the client is HTTP-shaped and gets
`respx` tests; the manifest builder is pure and gets straight pytest
assertions. Different test ergonomics, different files.

### New CLI command — `peerbench upload-workbook`

In `src/peerbench/cli.py`:

```python
@app.command("upload-workbook")
def upload_workbook_cmd(
    file: Path,          # --file <path-to-xlsx>
    anchor: int = 4063,  # --anchor <cert>
) -> None:
    """Upload the workbook + manifest to Supabase Storage."""
```

Resolves `quarter_id` by parsing the workbook filename
(`peerbench_<cert>_<quarter>.xlsx`), reads env vars via existing
`get_settings()`, calls `client.upload()` twice (`.xlsx` then `.json`).

Surfaces non-2xx responses via `typer.echo(..., err=True)` +
`raise typer.Exit(code=2)`, matching the existing ingest/compute pattern.

### Modified — `peerbench export --quarter latest` sentinel

One small change in `cli.py`'s `export_cmd`: if `quarter == "latest"`,
resolve to `MAX(quarters.quarter_id)` via a single
`session.scalar(select(func.max(Quarter.quarter_id)))` call. Keeps the
YAML free of date math.

## GitHub Action changes

Two appended steps at the bottom of `.github/workflows/daily-ingest.yml`,
after the existing `Compute ratios` step:

```yaml
- name: Generate workbook
  run: uv run peerbench export --quarter latest --output ./output

- name: Upload workbook to Supabase Storage
  run: |
    workbook=$(ls ./output/peerbench_*.xlsx | head -1)
    uv run peerbench upload-workbook --file "$workbook"
```

No new secrets — `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` are
already in the Action's `env` block. The `output/` directory is
gitignored and lives only for the runner's lifetime.

The export step writes to `./output/`; the upload step reads from it.
Runner is ephemeral so no cleanup is needed.

## Dashboard components

### `web/lib/workbook-manifest.ts`

Server-only fetcher. Exports:

```ts
export type WorkbookManifest = {
  url: string;
  generatedAt: string;  // ISO-8601 UTC
  quarterId: string;
  sizeBytes: number;
};

export async function fetchWorkbookManifest(): Promise<WorkbookManifest | null>;
```

Implementation notes:

- URL hardcoded to
  `${SUPABASE_URL}/storage/v1/object/public/peerbench-exports/latest.json`.
  `SUPABASE_URL` already in `web/.env` and Vercel env.
- `fetch(..., { next: { revalidate: 300 } })` — 5-minute server cache,
  well under the 24-hour regeneration cadence.
- 3-second timeout via `AbortController`.
- Hand-written `parseManifest` (no Zod — same approach as the rest of
  `web/lib`). Validates the four required fields and their types.
- Returns `null` on any failure mode (404, timeout, network, malformed
  JSON, wrong shape). Logs malformed/wrong-shape to `console.error` for
  Sentry capture.

### `web/components/workbook-download.tsx`

Server component. Pure markup, no client JS:

```tsx
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

Uses existing design tokens only — no new ones needed.

### Modified — `web/app/page.tsx`

Two-line change. The right-aligned subtitle row goes from one `<span>`
to a `<div>` holding both the "As of" date and the `<WorkbookDownload />`
component, stacked vertically. Existing
`mb-4 flex items-baseline justify-between gap-4` header layout is
preserved; the right slot expands.

### Modified — `web/lib/format.ts`

Add `formatRelativeDate(iso: string): string` — returns "today",
"yesterday", "3 days ago", or `"on May 15, 2026"` for >7 days old. Pure
function, ~10 lines, ~5 test cases. Lives next to existing
`formatReportDate`.

## Manifest JSON shape

```json
{
  "url": "https://<project>.supabase.co/storage/v1/object/public/peerbench-exports/latest.xlsx",
  "generated_at": "2026-05-24T03:07:42Z",
  "quarter_id": "2025-Q4",
  "anchor_cert": 4063,
  "size_bytes": 62513
}
```

## Error handling & failure modes

### Action-side

- **Export step fails** → workflow step fails → Action red. Existing
  GitHub email-on-failure notification fires. Ingest/compute already
  committed, so retry on next firing is harmless.
- **Upload step fails** (network blip, Supabase blip) → step fails →
  Action red. Bucket still serves the previous `latest.xlsx`+`latest.json`,
  so the dashboard keeps working with yesterday's workbook. The "Updated"
  subtitle gradually goes stale (1 → 2 → 3 days), giving the user a
  visual canary for sustained upload failures without a dedicated alert.
- **Service-role key invalid** → 401 from Storage API → upload step
  fails fast and loud with the response body in the runner log.
- **Manifest written before workbook** is the only ordering bug worth
  pre-empting. Upload `.xlsx` *first*, then `.json`. If `.xlsx`
  succeeds and `.json` fails, dashboard still shows the prior manifest
  pointing at the prior `.xlsx` — consistent, just stale. The reverse
  (manifest pointing at a `.xlsx` that hasn't been uploaded yet) would
  break the download link, so we never write the manifest first.

### Dashboard-side

- **Bucket 404 (first-run, before any Action firing)** → fetcher returns
  `null` → component renders nothing → page looks exactly like today.
- **Supabase Storage down / slow** → 3-second `AbortController` timeout
  → `null` on timeout. Matrix still renders; download just doesn't
  appear that request. Next request retries.
- **Manifest JSON malformed** → `parseManifest` returns `null` on shape
  mismatch. Logs via `console.error` so it surfaces in the browser
  devtools and in the Vercel runtime logs (Sentry capture of console
  errors is opt-in via `CaptureConsole` integration, not currently
  enabled — out of scope here).
- **Click-through 404** (link works in dashboard but `.xlsx` 404s) —
  shouldn't happen because we upload `.xlsx` before `.json`. If it
  does, the user gets the browser's native 404. Acceptable.

### Deliberately NOT building

- No retry loop in the upload step. GitHub Actions rerun is one click;
  one-day staleness is invisible to the user.
- No "stale workbook" warning banner. The relative-date subtitle
  already communicates freshness; a banner would clutter the header for
  a benign condition.
- No archive of past workbooks. Single `latest.xlsx` only,
  overwrite-on-upload semantics.

## Testing strategy

### Python (pytest, mirrors existing patterns)

```
tests/storage/
├── test_client.py        # ~6 cases via respx
└── test_manifest.py      # ~5 cases, pure-function assertions
```

`test_client.py` (respx mocks the Supabase Storage endpoint):

1. Successful upload (`200`) → no exception, correct headers
   (`Authorization`, `apikey`, `x-upsert: true`, `Content-Type`).
2. 4xx response → raises with response body in message.
3. 5xx response → raises with response body in message.
4. Network error → raises `httpx.ConnectError` un-swallowed.
5. Binary body (xlsx bytes) → correct
   `Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`.
6. JSON body (manifest) → correct `Content-Type: application/json`.

`test_manifest.py` (pure-function build):

1. Builds correct shape from real workbook file fixture.
2. `size_bytes` matches `os.stat`.
3. `generated_at` is a valid ISO-8601 UTC string with `Z` suffix.
4. `public_url_base` joined correctly (with and without trailing slash).
5. Anchor cert + quarter_id pass through untouched.

`tests/cli/test_upload_workbook.py` — one happy-path case using
`typer.testing.CliRunner` + `respx`. Verifies `--file` parses the
filename → `quarter_id`, both PUTs fire, exit code 0.

### Web (vitest, mirrors PR #16 / PR #17 / PR #18 patterns)

`web/lib/workbook-manifest.test.ts` — 6 cases, all mock `global.fetch`:

1. Valid JSON → returns parsed `WorkbookManifest`.
2. 404 → returns `null`.
3. Fetch times out (AbortController fires) → returns `null`.
4. Fetch throws (network error) → returns `null`.
5. Malformed JSON body → returns `null`, logs to console.
6. Wrong shape (missing required field) → returns `null`, logs to console.

`web/lib/format.test.ts` — extend with 5 new cases for
`formatRelativeDate`:

- today (`generated_at` within 24h of now)
- yesterday (24-48h)
- "3 days ago" (within 7 days)
- ">7 days" → absolute date format
- future date (clock skew) → "today"

### What we do NOT test

- **No vitest test for `workbook-download.tsx`** — it's a thin
  conditional render over `fetchWorkbookManifest` and
  `formatRelativeDate`, both already tested. React Testing Library
  isn't in the project (PR-D / PR-F established the pure-helper-only
  test pattern). Render correctness verified by smoke test.
- **No live Supabase integration test** — `pyproject.toml` has an
  `integration` marker for live-API tests. We don't add one for the
  upload path because it would (a) need a service-role key in pytest's
  env, (b) actually overwrite the prod bucket. Validated via the first
  real Action firing.

### Smoke test plan (manual, pre-merge)

1. Locally: `uv run peerbench export --quarter 2025-Q4 --output ./output && uv run peerbench upload-workbook --file ./output/peerbench_4063_2025-Q4.xlsx`
   against the real prod Supabase. End-to-end with real creds.
2. Locally: `cd web && npm run dev`, load `localhost:3000`, confirm
   "Download workbook" link appears with correct freshness subtitle,
   clicking it downloads the actual workbook.
3. Bucket inspection via Supabase MCP `execute_sql` (or dashboard) to
   confirm both objects landed.

### Sub-agent reviews (mirrors Sprint 2 / PR #19 pattern)

- `reviewer` sub-agent on the full diff before commit (no formula logic,
  manifest matches design tokens, no service-role key under `web/`).
- `design-critic` sub-agent on the dashboard diff (typography tokens,
  layout pressure on sticky header, freshness-subtitle color).
- `/codex review` as the pre-merge gate.

### Verification gate (mirrors PR #19)

- All existing tests still green: `uv run pytest -q` should report
  85 → ~97 (12 new cases: 6 client + 5 manifest + 1 CLI happy-path);
  `cd web && npm test` should report 144 → ~155 (11 new cases:
  6 manifest + 5 format).
- `npm run build` clean Turbopack compile.
- `pyright --strict` clean on `peerbench.storage` package.

## Prerequisites (one-time manual setup)

Before the first Action firing, create the Supabase Storage bucket:

1. Supabase dashboard → Storage → New bucket → name
   `peerbench-exports` → public → 1 GB cap (free tier).
2. Confirm public URL pattern:
   `https://<project>.supabase.co/storage/v1/object/public/peerbench-exports/<filename>`.
3. No RLS policy needed — public buckets bypass RLS by design.

This step is intentionally manual because it's a one-shot operation,
not worth automating with a Terraform/migration file.

## Out of scope

- **Archive of past workbooks.** Single `latest.xlsx` only.
  Re-introducing an archive would require date-stamped filenames + a
  bucket-listing UI in the dashboard. Not justified for the current
  user base (Connor + maybe a hiring committee).
- **Per-anchor workbook variants.** Today's `peerbench export --anchor`
  flag stays on the CLI for power-users. The dashboard download is
  always MidFirst-anchored (cert 4063), matching the dashboard's
  default-anchor behavior. If we eventually want per-anchor download,
  it slots in as a future PR: the Action loops on multiple anchors,
  uploads `latest_<cert>.xlsx`, dashboard reads the manifest matching
  the user's current `?anchor=` param.
- **Workbook history page.** Not needed.
- **Email notification when a new workbook lands.** GitHub Action
  failure email is sufficient.

## Definition of done

- [ ] `peerbench-exports` bucket exists in Supabase (manual prereq).
- [ ] `src/peerbench/storage/` package shipped with 11 passing tests.
- [ ] `peerbench upload-workbook` CLI command works locally against
      prod Supabase.
- [ ] `peerbench export --quarter latest` resolves to the most recent
      quarter_id.
- [ ] `.github/workflows/daily-ingest.yml` updated with export + upload
      steps; first real firing succeeds and uploads both
      `latest.xlsx` + `latest.json`.
- [ ] Dashboard at https://peerbench-web.vercel.app/ renders the
      "Download workbook (.xlsx)" link with correct freshness subtitle.
- [ ] Clicking the link downloads the same workbook
      `peerbench export` produces locally.
- [ ] Before the first Action firing, the dashboard renders nothing in
      the download slot (graceful empty-state).
- [ ] `reviewer` sub-agent PASS, `design-critic` sub-agent PASS,
      `/codex review` GATE PASS.
- [ ] All existing tests green; new tests green; `npm run build`
      clean; `pyright --strict` clean on the new package.

## Estimated effort

2-4 hours total (per the prior session's estimate):

- Python sub-package + tests: ~45 min
- CLI command + `--quarter latest` sentinel: ~20 min
- Workflow YAML changes + manual bucket setup: ~15 min
- Dashboard fetcher + component + format helper + tests: ~60 min
- Smoke test + sub-agent rounds + codex review: ~30-60 min
