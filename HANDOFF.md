# Peerbench — handoff (2026-05-21 evening, Phase 3 plumbing closed)

You are continuing work on Peerbench, Connor's FP&A internship-prep project at `/Users/connortipton/Projects/Peerbench`. Read `CLAUDE.md` and `PLAN.md` (v1.3) before doing anything substantive.

## TL;DR

- **Phase 3 plumbing fully closed.** Three PRs squash-merged today (2026-05-21):
  - **PR #3 @ `6f4385c`** — RLS migration (6 tables, 5 dashboard_read policies, `facts` service-only), FK covering indexes, daily-ingest cron, weekly pg_dump backup cron, ops runbook. Codex review reconciled pre-merge (1 P1 + 4 P2 all fixed; no findings deferred).
  - **PR #4 @ `bc208e8`** — bump weekly-backup `pg_dump` client 15 → 17 (Supabase is on Postgres 17.6, planning doc had assumed 15).
  - **PR #5 @ `4abac07`** — prepend `/usr/lib/postgresql/17/bin` to `$GITHUB_PATH` after install because GH Actions' ubuntu-latest pre-ships postgresql-client-16 and `pg_wrapper` was selecting v16 even with v17 installed alongside.
- **Live verification banked:**
  - 2 manual daily-ingest runs, the second producing **zero new `quality_log` rows** (idempotency proven via Supabase MCP query against the second run's window).
  - 1 manual weekly-backup run, ending with release `backup-2026-05-21-205053` (108 KB `*.sql.gz`, header confirms `Dumped from database version 17.6 / pg_dump 17.10` — majors match).
- **Test count: 78 passing** — unchanged by Phase 3 plumbing (no value-path code touched).
- **Working tree:** on `main` @ `4abac07`, clean.
- **DB state:** RLS enabled on all 6 public tables, `dashboard_read` policy on 5 of 6, `facts` intentionally service-role-only. Two FK covering indexes added.
- **All 8 repo secrets are populated** (`FDIC_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `DATABASE_URL` for Phase 3; `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `SENTRY_DSN`, `NEXT_PUBLIC_SENTRY_DSN` for Phase 3 PR #6).

## What landed this session (PRs #3, #4, #5)

### PR #3 — Phase 3 plumbing (squash-merge `6f4385c`)

Branch `phase-3-rls-cron-backup`. Nine commits squashed on merge (six implementation + three codex-fix follow-ups):

1. **`a6f2590` — `chore:` ignore .gstack/ tooling artifacts.**
2. **`fd855e7` — `feat(db):` enable RLS with permissive read policy.** `sql/migrations/0001_enable_rls.sql` — single BEGIN/COMMIT wrapping 6 ALTER TABLEs + 5 dashboard_read policies. `facts` intentionally RLS-on-no-policy (service-role bypasses; dashboard never reads facts directly per `web/lib/queries.ts:74`).
3. **`608e341` — `feat(db):` add FK covering indexes.** `sql/migrations/0002_add_fk_indexes.sql` — `facts.quarter_id` and `institutions.acquired_by` (cleared the 2 perf-advisor INFO findings).
4. **`a3a3645` — `feat(cron):` daily FDIC ingest workflow.** `.github/workflows/daily-ingest.yml` — 03:00 UTC schedule + manual_dispatch, sequential 5-cert for-loop (single `uv sync` cost), idempotent upserts, doubles as Supabase keepalive.
5. **`32ee2ec` — `feat(cron):` weekly pg_dump backup workflow.** `.github/workflows/weekly-backup.yml` — Sunday 04:00 UTC, uploads to private GitHub release, retains last 8 weekly dumps. DATABASE_URL must be session pooler (port 5432); transaction pooler (6543) silently rejects pg_dump.
6. **`4f56a4b` — `docs:` Phase 3 operations runbook.** `docs/operations.md` — manual triggers, RLS rollback procedure, restore-from-backup, CDR manual refresh pointer, heartbeat note, migration apply path.
7. **`74e5671` — codex P1 fix: enforce pipefail.** `defaults.run.shell: bash` at workflow level on `weekly-backup.yml` (implicit Linux runner shell is `bash -e {0}` without pipefail; `pg_dump | gzip` could have silently published empty/partial backup).
8. **`10d0a5e` — codex P2 fixes: SHA-pin actions + timestamp backup tag.** Pinned `actions/checkout@v4` and bumped `astral-sh/setup-uv` v3 → v8.1.0 (both SHA-pinned). Backup tag now `backup-YYYY-MM-DD-HHMMSS` for collision avoidance on same-day reruns.
9. **`fe66de5` — codex P2 fixes: ops doc accuracy + RLS smoke test.** Rewrote "Migration apply path" section to document the actual pg8000/SQLAlchemy apply path (Supabase MCP is read-only per CLAUDE.md). Added a post-rollback smoke test (anon SELECT institutions, anon SELECT facts blocked, dashboard renders, validate PASSes, advisor confirms).

**Codex review GATE on PR #3: FAIL → reconciled to clean.** 1 P1 (pipefail) + 4 P2s (backup-tag collision, SHA pinning, ops doc accuracy, RLS smoke test) all fixed on-branch; nothing deferred or justified.

### PR #4 — pg_dump 15 → 17 (squash-merge `bc208e8`)

First manual `workflow_dispatch` of `weekly-backup.yml` failed at the smoke step:

```
pg_dump: error: aborting because of server version mismatch
pg_dump: detail: server version: 17.6; pg_dump version: 16.13
```

Supabase upgraded the project to Postgres 17.6 (planning doc had assumed 15). Changed `postgresql-client-15` → `postgresql-client-17` in `weekly-backup.yml`. Pipefail caught the failure in 23 seconds with no empty/partial gzip artifact published.

### PR #5 — pg17 PATH prepend (squash-merge `4abac07`)

PR #4's `apt install postgresql-client-17` succeeded, but `pg_dump --version` still reported 16.13. Cause: GH Actions' ubuntu-latest pre-ships postgresql-client-16, and `/usr/bin/pg_dump` is `pg_wrapper` selecting v16 even with v17 installed alongside. Appended `/usr/lib/postgresql/17/bin` to `$GITHUB_PATH` after install so subsequent steps invoke the v17 binary directly. Verified live: `Dumped by pg_dump version 17.10` in the resulting release artifact.

## Open items / state of play

### Phase 1 — fully closed
- 29 of 30 ratios at `ok` across the 5×8 grid. `top_loan_cat` is `partial` (raises `NotImplementedError` — intentional defer).
- Restatement detector wired and producing audit-trail rows on each ingest.

### Phase 2 — Sprint 1 closed (PR #1 merged at `e000cc1`)
- Dashboard renders the 30-ratio × 5-peer matrix for the latest renderable quarter (2025-Q4). Real institution names, anchor tint on MidFirst column, sticky header + first column, design tokens from `docs/design.md` encoded in Tailwind v4 `@theme`.
- Restatement marker is per-cell (per `docs/design.md` spec), keyed by `(cert, ratio_id)`. The field→ratio mapping comes from `web/lib/ratio-field-deps.generated.json`, derived from handler ASTs by `peerbench export-field-deps`. Contract test `TestFieldDepsSnapshot` keeps it in lock-step with handler bodies.
- Load time: 812 ms in dev mode on localhost.

### Phase 2 — Sprint 2 onward (deferred)
- Per-peer sort, ratio category collapse/expand, drill-down detail view per `PLAN.md` v1.3.
- Restatement tooltip: `queries.ts` already pulls `old_value`/`new_value`/`detected_at` from `quality_log`; UI work remains.
- Cross-quarter recompute for `f.avg(...)` consumers (codex P2 from PR #1).
- Conditional formatting heat map, regulatory threshold amber flags.

### Phase 3 — plumbing closed (this session); deploy + observability remaining
- **Daily ingest cron: green ×2, idempotency proven.** Cron next fires 03:00 UTC on subsequent days; the "3 consecutive green daily runs on different days" DoD gate just needs calendar time (today=1, Fri+Sat will tick #2 and #3 automatically).
- **Weekly backup cron: green ×1, artifact verified.** Next scheduled fire is Sunday 04:00 UTC.
- **Vercel deploy NOT done.** PR #6 will land it.
- **Sentry NOT wired.** PR #6 will land it.
- **`actions/checkout` Node 20 → Node 24 — URGENT.** GH is force-bumping the Node runtime on June 2, 2026 (12 days from today). Current SHA pin is `actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5` (v4, Node 20). Need to bump to v5 or v6 (Node 24 native) in both `daily-ingest.yml` and `weekly-backup.yml` before then. Trivial 1-line PR per file.

### Phase 4 — polish (not started)
- Insights generation, Excel export from `ratios` table, README + Loom.

## What's NOT changed by Phase 3
- Handler bodies — untouched; AST snapshot clean. All handlers stay at `version="v1"` per the Phase 1 contract.
- `data/ratios.csv` — untouched.
- `tests/contract/handler_ast_snapshot.json` — untouched.
- Validation gate — untouched. `peerbench validate` still PASS at mean 0.02 bps / max 0.51 bps.
- `web/` — untouched. Dashboard still reads via anon key; RLS posture is transparent because dashboard reads only the 5 policied tables.

## Quick verify (run when picking up the session)

```bash
git -C /Users/connortipton/Projects/Peerbench log main -5 --oneline
# Expect (top to bottom):
#   4abac07 fix(cron): prepend pg17 bin dir to PATH after install (#5)
#   bc208e8 fix(cron): bump weekly-backup pg_dump client 15 → 17 (#4)
#   6f4385c Phase 3 — RLS + daily cron + weekly backup + runbook (#3)
#   982dbb4 docs(handoff): point next-chat prompt at Phase 3 hosting
#   58035aa docs(handoff): refresh post-PR-#1 — Sprint 1 closed, per-cell scoping landed

cd /Users/connortipton/Projects/Peerbench && uv run pytest 2>&1 | tail -3
# Expect: 78 passed

cd web && npm run build 2>&1 | tail -5
# Expect: clean build (no value-path code changed by Phase 3 plumbing)

gh run list --workflow=daily-ingest.yml --limit 3
# Expect: at least 1 ✓ run from today; subsequent ✓ runs on 03:00 UTC fires

gh release list --limit 3 | grep backup-
# Expect: backup-2026-05-21-205053 (108 KB)
```

If any diverge, surface to the user before doing substantive work.

## How to run things (smoke commands)

`.env.local` and `web/.env.local` are populated. All 8 repo secrets are populated for GH Actions.

```bash
# Python pipeline
uv run pytest                                       # 78 tests
uv run peerbench info                               # 30 handlers, 65 field codes
uv run peerbench ingest --cert 4063 --quarters 1    # FDIC API
uv run peerbench compute --cert 4063 --quarters 1   # compute ratios
uv run peerbench validate --certs 4063 --quarters 1 # bp diff vs FDIC precomputed
uv run peerbench export-field-deps                  # regenerate handler→field snapshot

# Dashboard
cd web && npm install && npm run dev                # http://localhost:3000

# Cron triggers (live)
gh workflow run daily-ingest.yml --ref main
gh workflow run weekly-backup.yml --ref main
gh run list --workflow=daily-ingest.yml --limit 5
gh release list --limit 5
```

## Architecture conventions to honor

(Also in `CLAUDE.md`; repeated so they survive into a fresh context.)

- **Decimal end-to-end.** No `float(` casts in the value path. Contract test enforces against `VALUE_PATH_MODULES`.
- **Ratio handler registry.** Every ratio has a row in `ratio_defs` AND a registered handler. Contract test enforces 1:1 + AST-hash drift detection.
- **All handler versions stay at `"v1"`.** Phase 1 hasn't shipped externally.
- **Handler field-dependency snapshot.** `peerbench export-field-deps` walks each handler's AST and writes `web/lib/ratio-field-deps.generated.json`. After any handler edit that touches field references, regenerate and commit.
- **No formula logic in TS or Excel.** Dashboard and (future) Excel export read `ratios.value` only.
- **Post-CECL nomenclature.** ACL, never ALLL.
- **RLS posture (NEW this session).** `dashboard_read` policy on `institutions`/`quarters`/`ratio_defs`/`ratios`/`quality_log`. `facts` is service-role-only (intentional RLS-on-no-policy). Pipeline writes via service-role key which bypasses RLS. Dashboard reads via anon key against the 5 policied tables. **Do not add an anon policy to `facts`** — the dashboard never queries it directly.
- **DATABASE_URL must be the session pooler (port 5432)** for `pg_dump` to work. Transaction pooler (6543) silently rejects `pg_dump`.
- **GH Actions runners ship postgresql-client-16 pre-installed.** Any future workflow that uses `pg_dump` against Supabase must explicitly prepend `/usr/lib/postgresql/17/bin` to `$GITHUB_PATH` after installing `postgresql-client-17` (see `weekly-backup.yml` for the pattern).
- **GitHub Actions implicit Linux shell is `bash -e {0}` (no pipefail).** Workflows that pipe data through `gzip`/`jq`/etc must set `defaults.run.shell: bash` at workflow level to get `-eo pipefail`. Pattern is in `weekly-backup.yml`.

## What NOT to redo

- **Don't re-stage CDR ZIPs** — `cache/cdr/2024-Q1.zip` … `2025-Q4.zip` are present (+ 2026-Q1.zip extra not yet used).
- **Don't re-apply institution names** — already in DB.
- **Don't re-ingest the 5 banks** unless explicitly asked. Re-ingest is idempotent.
- **Don't bump handler `version="v1"`** during Phase 1.
- **Don't trust BOK cert 4862 or Cullen/Frost cert 5560** — inactive. Use **4214** and **5510**.
- **Don't re-apply the RLS migration via Supabase MCP** — it's already applied via the project's pg8000/SQLAlchemy session. The committed `.sql` files in `sql/migrations/` are the audit trail.
- **Don't push pg_dump against the transaction pooler (6543)** — it silently fails. Session pooler (5432) only.

## Today's date

2026-05-21 (evening session). Most recent finalized quarter (90-day publication latency) is **2025-Q4** (`report_date = 2025-12-31`).

## User context / preferences

- Connor, prepping for Summer 2026 FP&A internship at MidFirst Bank.
- Solo developer, fresh repo, doubles as portfolio material.
- High autonomy ("just go with your best recommendations") but wants a heads-up before live DB changes, force-pushes, or other irreversible actions.
- Prefers check-ins at chunk boundaries; terse responses; no narration of every step.
- Uses `/codex review` as a routine pre-merge gate; treats codex P2s as worth fixing or explicitly justifying.
- For trivial fixes: branch + PR, then squash-merge after one-line confirmation. Same pattern is used for codex-review follow-ups on a larger PR.

## Recommended first action

**PR #6 — Vercel deploy + Sentry.** This closes the Phase 3 DoD ("production deploy live + Sentry receiving events"). Phase 3 plumbing observability gate ("3 consecutive green daily runs") is on its own clock and doesn't block this PR.

The plan is at `~/.claude/plans/next-chat-prompt-jolly-parrot.md`, "PR #4 — Vercel deploy + Sentry" section (yes, the file still numbers it #4 because the plan was written before PR #4 = pg-client fix and PR #5 = PATH prepend used the slot; the actual GitHub PR will be #6).

Outline:
1. **Sentry SDK ↔ Next.js 16 compat check first.** Query Context7 against `/websites/sentry_io_platforms_javascript_guides_nextjs` for "Next.js 16 Turbopack setup" before touching config. Confirm v8+ SDK supports Next 16.2.6 + React 19.2 + Turbopack stable, and that `npx @sentry/wizard@latest -i nextjs` is still the documented path.
2. **Run the Sentry wizard from `web/`.** Let it generate `instrumentation.ts`, `instrumentation-client.ts`, `sentry.server.config.ts`, `sentry.edge.config.ts`, `app/global-error.tsx`. Inspect every file it touched; back out any deviations from Peerbench conventions (no `any`, no formula logic in TS).
3. **Verify `withSentryConfig` keeps source-map upload conditional on `SENTRY_AUTH_TOKEN` presence** so local `npm run build` works without it.
4. **Vercel project setup** with Root Directory = `web`, framework = Next.js auto-detected. Production env vars: `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `NEXT_PUBLIC_SENTRY_DSN`, `SENTRY_DSN`, `SENTRY_AUTH_TOKEN` (sentry.io with `project:releases` scope), `SENTRY_ORG`, `SENTRY_PROJECT`. **Do not** set `SUPABASE_SERVICE_ROLE_KEY` in Vercel.
5. **Production smoke after first deploy:** page loads <1s, 30×5 matrix renders, restatement markers correct, design tokens applied, Sentry `captureException` lands in dashboard within 30s.
6. **`/codex review` before opening PR** (use the prompt template Connor's pasting separately).

### Urgent maintenance — wrap in a tiny PR before PR #6 if you want

**`actions/checkout` Node 20 deprecation.** GH force-bumps to Node 24 on **June 2, 2026** (12 days from today). The pin in both `daily-ingest.yml` and `weekly-backup.yml` is currently `actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5` (v4, Node 20). Bump to v5 or v6 (Node 24 native) — one-line edit per file, get SHAs via `gh api repos/actions/checkout/git/refs/tags/v5` (or v6). Acceptable to defer until after PR #6 if scope-managing; not acceptable to defer past June 2.

## Definition of done for PR #6 (per `PLAN.md` Phase 3 DoD + this session's reality)

- Production deploy live at a Vercel URL serving the 30 × 5 matrix.
- Sentry receiving events (Connor will smoke-test).
- Source-map upload conditional on `SENTRY_AUTH_TOKEN` (so local builds work without it).
- `/codex review` passes (P1 fixed on-branch, P2s decided).
- The "3 consecutive green daily-ingest runs on different days" gate ticks independently; doesn't block PR #6.
