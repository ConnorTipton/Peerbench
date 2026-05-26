# Peerbench operations runbook

Reference doc for the Phase 3 hosting layer. Not a tutorial — assumes
familiarity with `PLAN.md` and `CLAUDE.md`. For pipeline conventions
and architecture, see those documents first.

## Cron workflows

Two scheduled GitHub Actions in `.github/workflows/`.

| Workflow | When | What |
| --- | --- | --- |
| `daily-ingest.yml` | 03:00 UTC daily | `peerbench ingest` + `peerbench compute` for every cert in `data/peers.toml` (16 banks as of Phase 5.1) across the last 8 quarters. Doubles as the Supabase 7-day inactivity heartbeat. |
| `weekly-backup.yml` | Sunday 04:00 UTC | `pg_dump` of the live DB → gzipped → uploaded to a private GitHub release tagged `backup-YYYY-MM-DD`. Retains the 8 most recent backups. |

### Manual triggers

```bash
gh workflow run daily-ingest.yml
gh workflow run weekly-backup.yml
```

### Required repo secrets

Set under **Settings → Secrets and variables → Actions → New repository secret**:

- `FDIC_API_KEY` — optional; register at https://api.fdic.gov for rate-limit headroom.
- `SUPABASE_URL` — `https://<project-ref>.supabase.co`
- `SUPABASE_SERVICE_ROLE_KEY` — service role key from Supabase API settings. Bypasses RLS; pipeline-only.
- `DATABASE_URL` — Supabase **session pooler** URI (port 5432). **Not** the transaction pooler (6543) — `pg_dump` silently fails against it.

`GITHUB_TOKEN` is provided automatically; the backup workflow's `permissions: { contents: write }` block grants it release create/delete.

### Cron budget

Daily ~1–2 min/run × 30 days plus the weekly backup ≈ 35–65 min/month. Well under the 2,000 min/month GH Actions free private-repo cap.

## CDR ingest (manual, quarterly)

The daily cron does **not** include `peerbench ingest-cdr`. FFIEC's public bulk-download endpoint at https://cdr.ffiec.gov/CDR/Public/CDRDownload.aspx is ASP.NET VIEWSTATE form-driven and can't be automated with a plain HTTP GET; the `CdrClient` raises `CdrZipNotCachedError` when ZIPs are missing.

As of Phase 5.1, CDR data feeds 2 ratios (`cet1`, `htm_loss_t1`) plus
~45 Schedule RI / RC line items rendered on the `/statements` view. The
fields publish quarterly. The manual refresh procedure:

1. Visit https://cdr.ffiec.gov/CDR/Public/CDRDownload.aspx
2. Select "Subject Data Format" + the quarter you want (Call Reports publish ~30 days after quarter-end; restatements arrive on no fixed schedule)
3. Download the ZIP, save it to `cache/cdr/YYYY-Qn.zip`
4. Run locally:
   ```bash
   uv run peerbench ingest-cdr --certs "$(uv run peerbench list-peers --tier all --sep ,)" --quarters 8
   for cert in $(uv run peerbench list-peers --tier all); do
     uv run peerbench compute --cert "$cert" --quarters 8
   done
   ```
5. Verify the validation gate still passes:
   ```bash
   uv run peerbench validate --certs "$(uv run peerbench list-peers --tier all --sep ,)" --quarters 8
   uv run peerbench validate-statements --cert 4063 --quarter 2025-Q4
   ```

See `docs/cdr-ingest.md` for schedule-layout details, `docs/divergences.md`
for ratio-by-ratio status, and `docs/cdr-backfill.md` for the one-time
2020-2023 historical ingest that powers the `/statements` view's
24-quarter history.

## Peer management

The peer set is the source-of-truth list of banks Peerbench ingests and
renders on the dashboard. It lives in `data/peers.toml` — banker-editable,
diffable, hand-reviewed.

To add or remove a peer:

1. Edit `data/peers.toml`. Add/remove a `[[peers]]` entry. Use
   `scripts/resolve_certs.py` to look up FDIC cert numbers for new banks
   (one-shot, committed, not re-run).
2. Apply changes to the live DB:
   ```bash
   uv run peerbench sync-peers
   ```
   Idempotent: upserts `(cert, name, state, peer_tier)` on `institutions`.
3. Backfill or refresh data for the new peer:
   ```bash
   uv run peerbench ingest --cert <NEW_CERT> --quarters 8
   uv run peerbench ingest-cdr --certs <NEW_CERT> --quarters 8
   uv run peerbench compute --cert <NEW_CERT> --quarters 8
   ```
4. The next daily cron picks up the new cert automatically (the workflow
   reads from `peerbench list-peers` rather than a hard-coded list).

Tier conventions:

- `peer_tier = 1` — appears as a head-to-head column on the matrix and
  `/statements` view. Tier-1 includes the anchor (MidFirst, cert 4063).
- `peer_tier = 2` — distribution-only. Tier-2 banks contribute to a
  "Larger peer median" summary column but are never selectable as
  head-to-head columns. See `docs/handoffs` for the Phase 5 rationale.

## RLS rollback

`sql/migrations/0001_enable_rls.sql` enables Row Level Security on all 6 public tables. The dashboard depends on the permissive `dashboard_read` policies. To roll back if the dashboard breaks under RLS:

```sql
ALTER TABLE public.institutions DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.quarters     DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.ratio_defs   DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.ratios       DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.quality_log  DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.facts        DISABLE ROW LEVEL SECURITY;
```

The `dashboard_read` policies survive a `DISABLE` — they're just no-ops while RLS is off, so re-enabling is a single `ALTER TABLE ... ENABLE` per table without re-running the migration. Only `DROP POLICY "dashboard_read" ON public.<name>` for a permanent rollback.

### Post-rollback smoke test

After a `DISABLE` → `ENABLE` cycle, confirm RLS is correctly restored. Run via the Supabase MCP (read-only is fine):

1. Anon dashboard reads succeed:
   ```sql
   SELECT cert FROM public.institutions LIMIT 1;   -- expect 1 row
   SELECT ratio_id FROM public.ratios LIMIT 1;     -- expect 1 row
   ```
2. Anon `facts` reads are blocked (RLS-on-no-policy):
   ```sql
   SELECT * FROM public.facts LIMIT 1;             -- expect 0 rows
   ```
3. Dashboard renders end-to-end: `cd web && npm run dev` → load `http://localhost:3000` → confirm the 30 × 5 matrix renders with the expected 5 restatement markers (4 NIM consumers on MidFirst Cert 4063, 1 CET1 marker on Bank OZK Cert 110).
4. Pipeline still writes (service-role bypasses RLS):
   ```bash
   uv run peerbench validate --certs 4063,4214,110,11063,5510 --quarters 8
   ```
   Expect `Gate: PASS`.
5. Advisor confirms posture: `mcp__supabase__get_advisors type=security` — the 6 "RLS Disabled in Public" findings should NOT reappear.

## Restore from a backup release

Backup tags use second-level precision (`backup-YYYY-MM-DD-HHMMSS`) so same-day reruns don't collide.

```bash
# List recent backup tags
gh release list --limit 20 | grep backup-

# Download a specific backup (substitute the actual tag from the list)
gh release download backup-YYYY-MM-DD-HHMMSS --pattern "*.sql.gz"

# Sanity-check the dump
gunzip -c peerbench-*.sql.gz | head -50

# Restore into a SCRATCH DB first (do not restore in-place over a live DB).
# Easiest path: new Supabase project, then restore the dump, then update
# DATABASE_URL / SUPABASE_URL in the secrets to point at the new project.
psql "$SCRATCH_DATABASE_URL" -f <(gunzip -c peerbench-*.sql.gz)
```

In-place `psql` restores against the live DB are technically possible but require dropping existing rows or restoring to fresh tables — not recommended without a maintenance window.

## Heartbeat note

The daily cron is the **only** Supabase keepalive. Supabase free-tier projects pause after 7 days without activity. If the daily cron is red for 6+ consecutive days, the project will pause and a manual unpause is required (Supabase Dashboard → Project → Restore project). Re-running the cron after unpause restores normal operation.

## Migration apply path

Migrations land at `sql/migrations/0001_enable_rls.sql`, `0002_add_fk_indexes.sql`, etc. The committed `.sql` files in `sql/migrations/` are the audit trail. The Phase 3 migrations (`0001` + `0002`) have already been applied to the live Supabase project.

**Apply path:** run the migration file through the project's pg8000/SQLAlchemy session (the same connection the pipeline uses via `DATABASE_URL`), e.g.:

```bash
uv run python -c "
from sqlalchemy import text
from peerbench.db import get_engine
sql = open('sql/migrations/0001_enable_rls.sql').read()
with get_engine().begin() as conn:
    conn.execute(text(sql))
"
```

The Supabase MCP server is **read-only** in this project (per CLAUDE.md), so `mcp__supabase__apply_migration` is not the path we use. `mcp__supabase__list_migrations` will not show these applies; the `git log` on `sql/migrations/` is the authoritative record.

Migrations like `0001_enable_rls.sql` already contain an explicit `BEGIN/COMMIT`, so the file is atomic even when the SQLAlchemy session adds its own outer transaction wrapping.

**Do not apply migrations via the Supabase SQL Editor** — it leaves no trace in `git log` and bypasses the audit trail.

`sql/schema.sql` is the canonical end-state document. A fresh clone + apply of every migration in order should yield a DB equivalent to `sql/schema.sql`.

## Print verification

Phase 4.3 DoD: the dashboard must print cleanly to letter-size PDF. Re-verify on every PR touching `web/app/globals.css`, `web/components/ratio-matrix.tsx`, or `web/app/ratio/[ratio_id]/page.tsx`.

### Procedure

```bash
cd web
npm run build
npm start  # serves the production build on http://localhost:3000
```

In a second shell:

```bash
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
"$CHROME" --headless=new --disable-gpu --no-sandbox \
  --virtual-time-budget=10000 --no-pdf-header-footer \
  --print-to-pdf=docs/screenshots/print-summary.pdf \
  http://localhost:3000
"$CHROME" --headless=new --disable-gpu --no-sandbox \
  --virtual-time-budget=10000 --no-pdf-header-footer \
  --print-to-pdf=docs/screenshots/print-ratio-nim.pdf \
  http://localhost:3000/ratio/nim
```

`--virtual-time-budget=10000` gives Recharts ~10 seconds of virtual time to hydrate before the snapshot — without it, the trend and distribution charts capture as empty containers.

Manual alternative: open each URL in Chrome → Cmd-P → Save as PDF → US Letter → Default margins.

### Acceptance criteria

- Letter size (8.5×11in); 0.5in margins (`@page` rule in `globals.css`).
- Black text on white. No tints — anchor navy, quartile green/red, amber/red regulatory all dropped via the `*:not(svg, svg *)` color reset in `@media print`.
- Chrome hidden: `AnchorSelect`, `WorkbookDownload`, sort carets (`↑`/`↓`/`↕`), section-toggle chevrons (`▾`/`▸`), drilldown `← Matrix` link.
- Page-2 thead repeat shows the full header row (bank name + cert subtitle for all peers) — verifies the `print:hidden` `<button>` + `print:block` `<span>` sibling fallback pattern in `SortHeader` / `AnchorCertTrigger`.
- All 30 ratios visible on the matrix print across however many pages it takes; data rows never split mid-cell (`print:break-inside-avoid` on each data `<tr>`).
- Drilldown trend (page 2) + peer distribution (page 3) each on their own page (`print:break-before-page` on each `<section>`).
- Trend chart anchor line is distinctly heavier (2.5px) and in `--color-accent` navy; peers are 1px `--color-text-tertiary` gray. Strip-plot anchor dot is 6px navy; peer dots are 4px gray.
- Negatives in parentheses; numerics right-aligned; tabular-nums spacing intact.

### Known limitations

- **Collapsed-section rows are absent from the PDF.** `RatioMatrix` filters collapsed-category rows out of the TanStack row model at the React data layer, not via CSS. If a user collapses a category before printing, that category's ratios are absent from the PDF. Print after expanding all categories to capture the full set.
- **Strip-plot on drilldown page 3 sits flush-left at ~55% width.** Cosmetic — the underlying `ResponsiveContainer` computes a narrower width in the print viewport than expected. The chart data is correct; the framing is just under-sized. Tracked as a Phase 4.3 follow-up.
