# Peerbench operations runbook

Reference doc for the Phase 3 hosting layer. Not a tutorial — assumes
familiarity with `PLAN.md` and `CLAUDE.md`. For pipeline conventions
and architecture, see those documents first.

## Cron workflows

Two scheduled GitHub Actions in `.github/workflows/`.

| Workflow | When | What |
| --- | --- | --- |
| `daily-ingest.yml` | 03:00 UTC daily | `peerbench ingest` + `peerbench compute` for the 5-bank slice (4063, 4214, 110, 11063, 5510) across the last 8 quarters. Doubles as the Supabase 7-day inactivity heartbeat. |
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

CDR data feeds 2 of 30 ratios (`cet1`, `htm_loss_t1`) and publishes quarterly. The manual refresh procedure:

1. Visit https://cdr.ffiec.gov/CDR/Public/CDRDownload.aspx
2. Select "Subject Data Format" + the quarter you want (Call Reports publish ~30 days after quarter-end; restatements arrive on no fixed schedule)
3. Download the ZIP, save it to `cache/cdr/YYYY-Qn.zip`
4. Run locally:
   ```bash
   uv run peerbench ingest-cdr --certs 4063,4214,110,11063,5510 --quarters 8
   uv run peerbench compute --cert 4063 --quarters 8   # (and other certs)
   ```
5. Verify the validation gate still passes:
   ```bash
   uv run peerbench validate --certs 4063,4214,110,11063,5510 --quarters 8
   ```

See `docs/cdr-ingest.md` for the schedule layout details and `docs/divergences.md` for ratio-by-ratio status.

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

## Restore from a backup release

```bash
# Pick a backup tag
gh release list --limit 20 | grep backup-

# Download
gh release download backup-YYYY-MM-DD --pattern "*.sql.gz"

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

Migrations land at `sql/migrations/0001_enable_rls.sql`, `0002_add_fk_indexes.sql`, etc.

**Apply via Supabase MCP** (`mcp__supabase__apply_migration`) — single source of truth for what's been applied. The MCP wraps each migration call in a transaction; for migrations like `0001_enable_rls.sql` that already contain an explicit `BEGIN/COMMIT`, that's belt-and-suspenders but safe.

**Do not apply migrations via the Supabase SQL Editor** — it bypasses the MCP's migration tracking. If you ever need a manual apply, also record it in `mcp__supabase__list_migrations`.

`sql/schema.sql` is the canonical end-state document. A fresh clone + apply should yield a DB equivalent to running the migration sequence in order.
