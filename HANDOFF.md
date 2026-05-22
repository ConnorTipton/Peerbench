# Peerbench — handoff (2026-05-22 night, PR #11 merged — cross-quarter recompute closed)

You are continuing work on Peerbench, Connor's FP&A internship-prep project
at `/Users/connortipton/Projects/Peerbench`. Read `CLAUDE.md` and `PLAN.md`
(v1.3) before doing anything substantive.

## TL;DR

- **PR #11 merged at `a0cfbdd`** (Phase 2 Sprint 2 first item).
  Restatement detector now issues a forward-quarter `UPDATE ratios SET
  data_quality='partial'` for rows whose `f.avg(...)` window reaches back
  through a restated quarter — closes the codex P2 from PR #1. Direct
  consumers today: `nco_ratio` (LNLSGR). Transitive via
  `RATIO_DEPENDENCIES`: `nis` ← `cost_funds` ← DEPI. Forward window is
  `(Y, Qn+1..Q4)` same-year and `(Y+1, Q1..Q4)` on Q4 restatements.
  Zero handler bodies touched; AST snapshot unchanged; all handlers stay
  at `version="v1"`.
- **Phase 3 fully closed in production.** Five PRs squash-merged on
  2026-05-22 on top of the plumbing landed yesterday:
  - **PR #6 @ `75e5205`** — Vercel deploy + Sentry. Hand-configured Sentry on
    Next.js 16 + Turbopack (`@sentry/nextjs@10.53.1`), v8+ layout
    (`instrumentation.ts` + `instrumentation-client.ts` +
    `sentry.{server,edge}.config.ts` + `app/global-error.tsx`).
    `withSentryConfig` wrap; source-map upload conditional on
    `SENTRY_AUTH_TOKEN`. Codex review PASS, 0 findings.
  - **PR #7 @ `7f177d2`** — sticky table header + first column fix
    (Phase 2 Sprint 1 DoD bug, pre-existing on main since PR #1). 3-line
    diff: `<main>` is now `flex h-dvh flex-col`, matrix wrapper is
    `flex-1 min-h-0 overflow-auto`, table is `border-separate border-spacing-0`.
    (The `h-dvh` + `min-h-0` refinement came in via PR #10.)
  - **PR #8 @ `eac9f16`** — Sentry tunnel route (`/monitoring`) to bypass
    ad blockers. 3-line diff to `next.config.ts`.
  - **PR #9 @ `8492adb`** — `actions/checkout` v4 → v6.0.2 (Node 24 native,
    ahead of GitHub's 2026-06-02 Node-runtime force-bump). 2-line diff to
    `.github/workflows/{daily-ingest,weekly-backup}.yml`. Codex review on
    the cumulative #7/#8/#9 diff: GATE PASS, 0 P1; both P2s landed via
    PR #10; 1 P3 deferred.
  - **PR #10 @ `14a7a13`** — codex P2 hotfix against the PR #7 surface.
    `<main>` `h-screen` → `h-dvh` (mobile Safari URL-bar quirk), add
    `min-h-0` to the matrix `flex-1 overflow-auto` wrapper (robust
    contained scrolling), section header row `border-y` → `border-b`
    (kills double separator under `border-separate`). 3-line diff.
- **Live verification banked today:**
  - Production deploy: https://peerbench-web.vercel.app/ — HTTP 200,
    warm TTFB 330–600 ms (DoD target <1 s), 30×5 ratio matrix renders,
    MidFirst anchor tint, 5 restatement markers in the expected cells.
  - Sentry: **30 server transactions captured** on the Next.js Overview
    dashboard (project `peerbench-web` under org `peerbench`).
    `GET /` avg 274 ms / P95 386 ms — same data as the curl TTFB, different
    vantage point.
  - Daily-ingest scheduled cron fired green at **2026-05-22T06:48 UTC**
    (delay from the 03:00 UTC schedule is normal free-tier behavior).
    First scheduled run after PR #5; second + third firings expected
    2026-05-23 and 2026-05-24.
- **Test count: 85 passing** (+7 from PR #11's
  `TestQualityLogCallbackCrossQuarter` + field-deps walker tests). No
  value-path code touched (handler bodies unchanged).
- **Working tree:** on `main` @ `a0cfbdd`, clean. Feature branch
  `phase-2-cross-quarter-recompute` deleted on merge.

## What landed this session (PRs #6, #7, #8, #9, #10, #11)

### PR #6 — Phase 3 hosting (squash-merge `75e5205`)

Branch `phase-3-vercel-sentry`. Two commits squashed on merge:

1. **`6ee4f1c` — `feat(web):` wire Sentry for Vercel deploy.** Hand-config
   (no wizard) so the diff stays lint-clean and convention-aligned. Five
   new files under `web/`:
   - `instrumentation.ts` — server/edge runtime bootstrap +
     `onRequestError = Sentry.captureRequestError`.
   - `instrumentation-client.ts` — browser init + `onRouterTransitionStart`.
     `tracesSampleRate: 0.1` in prod, `1.0` in dev. `enabled: NODE_ENV === "production"`.
   - `sentry.server.config.ts` + `sentry.edge.config.ts` — runtime configs,
     mirror the client init at 0.1 sample rate, production-only.
   - `app/global-error.tsx` — React error boundary; the only client
     component in the diff (Sentry framework requirement).
   - `next.config.ts` — `withSentryConfig` wrap;
     `sourcemaps.disable: !process.env.SENTRY_AUTH_TOKEN`, `silent: !CI`.
2. **`957b2d6` — `ci:` trigger preview deploy** (empty commit, squashed
   away on merge; was needed to fire the GitHub-Vercel webhook for the
   first preview build after project creation).

**Verification on merge:** local build with `SENTRY_AUTH_TOKEN` set uploaded
99 source-map files to Sentry under release `6ee4f1c…`; `npm run lint` 0
errors; `uv run pytest` 78 passing; codex review PASS with 0 findings.

### PR #7 — sticky table header fix (squash-merge `7f177d2`)

Branch `phase-2-fix-sticky-table-header`. Two compounding root causes
were defeating `position: sticky` on `<th>`/`<td>`:

1. **Matrix wrapper had `overflow-auto` with no height constraint** →
   the wrapper expanded vertically to fit the table, vertical scrolling
   happened on `<body>`, and the sticky cells stuck to the wrapper's top
   edge (which itself scrolled away with the body).
2. **`border-collapse: collapse`** has a known Chrome/Safari quirk
   where borders break or disappear on sticky cells.

Fix (3 lines):

- `web/app/page.tsx`: `<main>` → `flex h-screen flex-col` (viewport-height
  flex column).
- `web/components/ratio-matrix.tsx`: wrapper → `flex-1 overflow-auto`
  (real scroll container with constrained height).
- `web/components/ratio-matrix.tsx`: table → `border-separate
  border-spacing-0` (avoids the border-collapse / sticky-cell conflict;
  existing per-cell `border-b` / `border-r` already use bottom+right
  conventions so no double borders).

### PR #8 — Sentry tunnel route (squash-merge `eac9f16`)

Branch `phase-3-sentry-tunnel-route`. Surfaced during PR #6 prod-smoke:
client SDK was firing Sentry events correctly but Connor's browser
ad blocker (uBlock / Brave Shields / similar) was matching the
`*.ingest.sentry.io` URL pattern and dropping the requests with
`ERR_BLOCKED_BY_CLIENT`. Server-side events were unaffected.

Fix (1 line): add `tunnelRoute: "/monitoring"` to `withSentryConfig`
options. Sentry's build plugin injects a Next.js route handler at
`/monitoring` that proxies events to Sentry server-side. Same-origin
POSTs bypass ad blockers — for most users.

(Connor's specific blocker also matches on the `/monitoring?o=…` query
pattern, so client events from his browser are still blocked. Not a
problem for the DoD or for other users; for portfolio demos on default
Chrome, the tunnel works.)

### PR #9 — actions/checkout v4 → v6.0.2 (squash-merge `8492adb`)

Branch `chore-actions-checkout-node24`. Single commit `bfcb601` → squash.

**Why now:** GitHub Actions force-bumps the Node runtime for
JavaScript-based actions from Node 20 to Node 24 on **2026-06-02**
(11 days out). `actions/checkout@v4` is Node-20-based and will fail
hard on or shortly after that date.

**Diff (2 lines):**

```diff
- - uses: actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5  # v4
+ - uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd  # v6.0.2
```

Applied to both `daily-ingest.yml` and `weekly-backup.yml`. SHA-pin
discipline preserved (PR #3's convention); the `# v6.0.2` comment is
human-readable but the SHA is the contract.

**Why v6 (not v5):** v6.0.0 cut 2025-11-20, v6.0.2 is the current patch
(2026-01-09, tag-handling bug fix). Both v5 and v6 are Node 24 native.
Both workflows use default checkout with no `with:` inputs, so the
v5→v6 surface changes (auth style cleanup, fetch-tags refspec
behavior) have zero blast radius. v6 also moves credential persistence
to `$RUNNER_TEMP`, but neither workflow uses Docker container actions
or authenticated git operations beyond initial checkout, so no behavior
delta.

### PR #10 — codex P2 hotfix (squash-merge `14a7a13`)

Branch `fix-sticky-table-borders-and-viewport`. Single commit `753dba0`
→ squash. Closes the two P2 findings from the cumulative codex review of
PRs #7/#8/#9.

**Diff (3 lines):**

- `web/app/page.tsx:25` — `flex h-screen flex-col` → `flex h-dvh flex-col`.
  Mobile Safari's dynamic URL bar makes `100vh` overflow the actual
  visible viewport; `100dvh` resolves to the visible area on every
  client.
- `web/components/ratio-matrix.tsx:112` — added `min-h-0` to the
  `flex-1 overflow-auto` wrapper. Default `min-height: auto` on a flex
  item can prevent shrink-to-fit; explicit `min-h-0` makes contained
  scrolling robust on every viewport.
- `web/components/ratio-matrix.tsx:152` — section row
  `border-y border-border` → `border-b border-border`. Under
  `border-separate border-spacing-0`, the top border doubled against
  the preceding data row's `border-b`. Single-sided separator now.

Pure Tailwind class changes; no runtime behavior change; lint clean.

**Codex cumulative review reconciled:** GATE PASS (0 P1). Both P2s
shipped via this PR. 1 P3 remains — anchor tint `6%` hardcoded as
inline style at `ratio-matrix.tsx:133`. Deferred to the Phase 4 design
pass; informational, not blocking.

### PR #11 — cross-quarter recompute for f.avg consumers (squash-merge `a0cfbdd`)

Branch `phase-2-cross-quarter-recompute`. Closes the codex P2 from PR #1:
when a Qn restatement landed, the detector only flipped the same-quarter
`ratios` row to `data_quality='partial'` — but YTD-averaging handlers
(`f.avg(field, periods=f.quarter_number + 1)`) consume that restated value
across the rest of the FDIC year (and into the next year for Q4
restatements). Until the next compute pass, the dashboard rendered stale
forward-quarter values with no indicator.

**Diff (4 files, +456/-13, zero handler bodies touched):**

- `src/peerbench/ingest/quality_log.py` (+92) — restatement detector now
  issues a second `UPDATE ratios SET data_quality='partial'` for forward
  quarters whose `f.avg(...)` window reaches back through the restated
  quarter. Same-quarter behavior unchanged.
- `src/peerbench/ratio_engine/field_deps.py` (+111, new file) — AST walker
  that resolves which handlers consume a given field via `f.avg(...)`,
  walking `RATIO_DEPENDENCIES` for transitive consumers (so DEPI →
  `cost_funds` → `nis` flips together).
- `tests/contract/test_ratio_registry.py` (+124) — contract test that the
  field-deps walker stays in sync with handler ASTs.
- `tests/unit/test_quality_log_callback.py` (+142) — new
  `TestQualityLogCallbackCrossQuarter` class covering:
  - LNLSGR @ 2025-Q2 → forward flip on Q3 + Q4 `nco_ratio` only.
  - LNLSGR @ 2024-Q4 → forward flip on `2025-Q1..Q4` (next-year rollover).
  - DEPI @ 2025-Q1 → forward flip on `cost_funds` AND `nis` (transitive);
    `yield_ea` correctly excluded.
  - NIM @ 2025-Q2 → exactly ONE UPDATE (no forward flip for non-`f.avg`).
  - Unconsumed field → zero UPDATEs (defensive parity).

**Forward-affected window pattern** (under
`periods=f.quarter_number + 1`):

- `(Y, Q1..Q3)` restatement → `(Y, Q+1..Q4)`.
- `(Y, Q4)` restatement → `(Y+1, Q1..Q4)` (Q4 is the prior year-end
  balance every Y+1 quarter averages in).

**Verification on merge:** codex review GATE PASS with 0 findings on the
diff. 85/85 tests pass. Vercel rebuild succeeded (no `web/` changes, no-op
rebuild); prod URL `https://peerbench-web.vercel.app/` HTTP 200, 1.6s
warm load. Deploy report at `.gstack/deploy-reports/2026-05-22-pr11-deploy.md`.

## Open items / state of play

### Phase 1 — fully closed

- 29 of 30 ratios at `ok` across the 5×8 grid. `top_loan_cat` is
  `partial` (raises `NotImplementedError` — intentional defer to Phase 4).
- Restatement detector wired; produces audit-trail rows on every ingest.

### Phase 2 — Sprint 1 closed

- Dashboard renders the 30-ratio × 5-peer matrix for the latest renderable
  quarter (2025-Q4). Real institution names, anchor tint on MidFirst column,
  **sticky header + first column now actually sticky on scroll (PR #7),
  with mobile-Safari-safe `h-dvh` viewport + clean single-line section
  separators (PR #10)**, design tokens from `docs/design.md` encoded in
  Tailwind v4 `@theme`.
- Restatement marker is per-cell, keyed by `(cert, ratio_id)`. The
  field→ratio mapping comes from `web/lib/ratio-field-deps.generated.json`,
  derived from handler ASTs by `peerbench export-field-deps`. Contract
  test `TestFieldDepsSnapshot` keeps it in lock-step with handler bodies.
- Load time: warm TTFB 330–600 ms on production (Vercel Hobby, US-East
  function region matching Supabase region). Sentry's server-transaction
  panel confirms `GET /` avg 274 ms / P95 386 ms over the first 30 hits.

### Phase 2 — Sprint 2 onward (deferred)

- Per-peer sort, ratio category collapse/expand, drill-down detail view
  per `PLAN.md` v1.3.
- Restatement tooltip: `web/lib/queries.ts` already pulls
  `old_value`/`new_value`/`detected_at` from `quality_log`; UI work
  remains. PR #11 now flips forward-quarter `data_quality='partial'`
  too, so the per-cell indicator already lights up on transitive
  consumers — only the tooltip surface is missing.
- ~~Cross-quarter recompute for `f.avg(...)` consumers (codex P2 from
  PR #1).~~ **Closed by PR #11 @ `a0cfbdd`.**
- Conditional formatting heat map, regulatory threshold amber flags.

### Phase 3 — closed end-to-end

- **Production deploy live:** https://peerbench-web.vercel.app/ (Root
  Directory = `web/`, Function Region `iad1` = Washington D.C. East,
  matching Supabase US East). No `vercel.json` (project setting handles
  subdirectory deploy natively).
- **Sentry receiving events:** confirmed via the Next.js Overview
  dashboard showing 30 captured `GET /` server transactions. `tunnelRoute:
  "/monitoring"` (PR #8) makes client events ad-blocker-resilient for
  the majority of users.
- **Daily ingest cron:** scheduled run today at 06:48 UTC succeeded
  (first scheduled run after PR #5's PATH fix). For the "3 consecutive
  green daily runs" DoD bullet, this is **1 of 3**; the next two firings
  are 2026-05-23 ~03:00 UTC and 2026-05-24 ~03:00 UTC (free-tier
  scheduling drifts by a few hours; that's normal and not a regression).
- **Weekly backup cron:** last green firing 2026-05-21T20:50 UTC
  (release `backup-2026-05-21-205053`, 108 KB). Next scheduled fire:
  2026-05-24T04:00 UTC.
- **PR #9 (actions/checkout v6 bump):** MERGED at `8492adb`. Cumulative
  codex review of PRs #7/#8/#9 reconciled clean (0 P1; 2 P2s landed via
  PR #10; 1 P3 deferred). Node 20 deadline closed 11 days early.

### Phase 4 — not started

- Insights generation (3 commentary bullets per peer/quarter pair).
- Excel comp workbook export (`uv run peerbench export`).
- Banking design pass (tabular-nums everywhere, conditional formatting,
  print CSS).
- README + ARCHITECTURE + Loom + screenshots.

## What's NOT changed by this session

- Handler bodies — untouched; AST snapshot clean. All handlers stay at
  `version="v1"` per the Phase 1 contract.
- `data/ratios.csv` — untouched.
- `tests/contract/handler_ast_snapshot.json` — untouched.
- Validation gate — untouched. `peerbench validate` still PASS at mean
  0.02 bps / max 0.51 bps.
- RLS posture — unchanged from PR #3. Dashboard reads via anon key
  against the 5 policied tables; `facts` stays service-role-only.
- SQL migrations. (GH Actions workflows changed in PR #9 — checkout SHA
  bump only; no behavior change.)

## Quick verify (run when picking up the session)

```bash
git -C /Users/connortipton/Projects/Peerbench log main -8 --oneline
# Expect (top to bottom):
#   <new HANDOFF commit>  docs(handoff): post-PR-#11 — cross-quarter recompute closed
#   a0cfbdd  fix(ingest): forward-quarter flip for f.avg consumers (codex P2 from PR #1) (#11)
#   0f0f010  docs(handoff): post-PRs-#9/#10 — Sprint 2 next
#   14a7a13  fix(web): h-dvh viewport + remove section row double border (#10)
#   8492adb  chore(ci): bump actions/checkout v4 → v6.0.2 (Node 24 native) (#9)
#   4804a00  docs(handoff): post-PR-#8 — Phase 3 closed on prod, PR #9 open
#   eac9f16  feat(web): proxy Sentry events through /monitoring tunnel
#   7f177d2  fix(web): sticky table header + first column on scroll

cd /Users/connortipton/Projects/Peerbench && uv run pytest 2>&1 | tail -3
# Expect: 85 passed

cd web && npm run lint 2>&1 | tail -3
# Expect: 0 errors, 1 warning (pre-existing TanStack memo warning at ratio-matrix.tsx:109).

cd web && npm run build 2>&1 | tail -8
# Expect: clean Turbopack compile. If SENTRY_AUTH_TOKEN is set,
# runAfterProductionCompile takes ~7-9s (source-map upload). Otherwise
# it takes <500ms (upload skipped).

gh run list --workflow=daily-ingest.yml --limit 5
# Expect: today's 06:48 UTC scheduled run = success; tomorrow + the
# day after should add two more green entries (~03:00 UTC each).

curl -sI https://peerbench-web.vercel.app/ | head -3
# Expect: HTTP/2 200, server: Vercel.
```

If any diverge, surface to the user before doing substantive work.

## How to run things (smoke commands)

`.env.local` (repo root) and `web/.env.local` are populated. All 8 repo
secrets are populated for GH Actions. All 7 production env vars are set
in Vercel (`peerbench-web` project, Production + Preview scopes).

```bash
# Python pipeline
uv run pytest                                       # 78 tests
uv run peerbench info                               # 30 handlers, 65 field codes
uv run peerbench ingest --cert 4063 --quarters 1    # FDIC API
uv run peerbench compute --cert 4063 --quarters 1   # compute ratios
uv run peerbench validate --certs 4063 --quarters 1 # bp diff vs FDIC precomputed
uv run peerbench export-field-deps                  # regenerate handler→field snapshot

# Dashboard (local)
cd web && npm install && npm run dev                # http://localhost:3000

# Dashboard (production)
open https://peerbench-web.vercel.app/

# Cron triggers (live)
gh workflow run daily-ingest.yml --ref main
gh workflow run weekly-backup.yml --ref main
gh run list --workflow=daily-ingest.yml --limit 5
gh release list --limit 5

# Sentry observability
open https://peerbench.sentry.io/projects/peerbench-web/
```

## Architecture conventions to honor

(Also in `CLAUDE.md`; repeated so they survive into a fresh context.)

- **Decimal end-to-end.** No `float(` casts in the value path. Contract
  test enforces against `VALUE_PATH_MODULES`.
- **Ratio handler registry.** Every ratio has a row in `ratio_defs` AND
  a registered handler. Contract test enforces 1:1 + AST-hash drift
  detection.
- **All handler versions stay at `"v1"`.** Phase 1 hasn't shipped externally.
- **Handler field-dependency snapshot.** `peerbench export-field-deps`
  walks each handler's AST and writes
  `web/lib/ratio-field-deps.generated.json`. After any handler edit that
  touches field references, regenerate and commit.
- **No formula logic in TS or Excel.** Dashboard and (future) Excel
  export read `ratios.value` only.
- **Post-CECL nomenclature.** ACL, never ALLL.
- **RLS posture (PR #3).** `dashboard_read` policy on
  `institutions`/`quarters`/`ratio_defs`/`ratios`/`quality_log`. `facts`
  is service-role-only (intentional RLS-on-no-policy). Pipeline writes
  via service-role key which bypasses RLS. Dashboard reads via anon
  key against the 5 policied tables. **Do not add an anon policy to
  `facts`** — the dashboard never queries it directly.
- **DATABASE_URL must be the session pooler (port 5432)** for `pg_dump`
  to work. Transaction pooler (6543) silently rejects `pg_dump`.
- **GH Actions runners ship postgresql-client-16 pre-installed.** Any
  future workflow that uses `pg_dump` against Supabase must explicitly
  prepend `/usr/lib/postgresql/17/bin` to `$GITHUB_PATH` after installing
  `postgresql-client-17` (see `weekly-backup.yml` for the pattern).
- **GitHub Actions implicit Linux shell is `bash -e {0}` (no pipefail).**
  Workflows that pipe data through `gzip` / `jq` / etc. must set
  `defaults.run.shell: bash` at workflow level to get `-eo pipefail`.
  Pattern is in `weekly-backup.yml`.
- **Sentry env-var split (PR #6).** `NEXT_PUBLIC_SENTRY_DSN` and
  `SENTRY_DSN` are identical and safe to expose (DSN is a public
  write-only token). `SENTRY_AUTH_TOKEN`, `SENTRY_ORG`, `SENTRY_PROJECT`
  are build-time, set in Vercel only. `SUPABASE_SERVICE_ROLE_KEY` must
  **NEVER** appear under `web/` or in Vercel — the dashboard uses the
  anon key only.
- **Sentry source-map upload is conditional on `SENTRY_AUTH_TOKEN`**
  (PR #6 / `next.config.ts` `sourcemaps.disable: !process.env.SENTRY_AUTH_TOKEN`).
  Local `npm run build` without the token succeeds with the upload
  skipped; Vercel builds with the token set publish maps. Both paths
  are exercised in CI by the silent fallback.
- **Sentry tunnel route is `/monitoring`** (PR #8 /
  `next.config.ts` `tunnelRoute: "/monitoring"`). Same-origin Next.js
  Route Handler injected by `withSentryConfig`. Adds ~1 Vercel
  serverless invocation per Sentry event; comfortably inside Hobby
  1M/month quota at our `tracesSampleRate: 0.1`.
- **Sticky table layout (PR #7 + PR #10).** `app/page.tsx`'s `<main>` is
  `flex h-dvh flex-col`; the matrix wrapper inside `RatioMatrix` is
  `flex-1 min-h-0 overflow-auto`; the `<table>` uses `border-separate
  border-spacing-0`. Don't refactor any of these four pieces in
  isolation — sticky behavior depends on all of them, and `min-h-0`
  specifically defends against the default `min-height: auto` on flex
  items preventing shrink-to-fit. Section rows use `border-b` only
  (not `border-y`) to avoid double separators with the preceding data
  row's bottom border.

## What NOT to redo

- **Don't re-stage CDR ZIPs** — `cache/cdr/2024-Q1.zip` …
  `2025-Q4.zip` are present (+ 2026-Q1.zip extra not yet used).
- **Don't re-apply institution names** — already in DB.
- **Don't re-ingest the 5 banks** unless explicitly asked. Re-ingest is
  idempotent.
- **Don't bump handler `version="v1"`** during Phase 1.
- **Don't trust BOK cert 4862 or Cullen/Frost cert 5560** — inactive.
  Use **4214** and **5510**.
- **Don't re-apply the RLS migration via Supabase MCP** — it's already
  applied via the project's pg8000/SQLAlchemy session. The committed
  `.sql` files in `sql/migrations/` are the audit trail.
- **Don't push `pg_dump` against the transaction pooler (6543)** —
  silently fails. Session pooler (5432) only.
- **Don't re-create the Vercel project** — it's set up with Root
  Directory `web/` and all 7 env vars (Production + Preview). Just
  push to `main` and it auto-deploys.
- **Don't rename the Sentry tunnel route** unless we explicitly hit
  a real-user blocker problem (i.e. low client transactions vs server
  transactions over a longer time window). Renaming is cat-and-mouse
  with ad-blocker lists.
- **Don't add `SUPABASE_SERVICE_ROLE_KEY` to Vercel.** The dashboard
  reads via anon key only.

## Today's date

2026-05-22 (evening session). Most recent finalized quarter (90-day
publication latency) is **2025-Q4** (`report_date = 2025-12-31`).

## User context / preferences

- Connor, prepping for Summer 2026 FP&A internship at MidFirst Bank.
- Solo developer, fresh repo, doubles as portfolio material.
- High autonomy ("just go with your best recommendations") but wants
  a heads-up before live DB changes, force-pushes, or other irreversible
  actions.
- Prefers check-ins at chunk boundaries; terse responses; no narration
  of every step.
- Uses `/codex review` as a routine pre-merge gate; treats codex P2s
  as worth fixing or explicitly justifying.
- For trivial fixes: branch + PR, then squash-merge after one-line
  confirmation. Same pattern is used for codex-review follow-ups on
  a larger PR.
- Sensitive secrets (auth tokens) get pasted into files directly via
  the IDE, never into chat. DSN values, project IDs, and org slugs
  are public/safe to discuss in chat.

## Recommended first action

**Phase 3 DoD calendar gate (passive).** Daily-ingest cron is at 1 of 3
required green firings. Next two are scheduled for 2026-05-23 ~03:00 UTC
and 2026-05-24 ~03:00 UTC (free-tier delay of a few hours is normal). No
action required — check `gh run list --workflow=daily-ingest.yml --limit 5`
on each of those days. Once the third lands, Phase 3 is DoD-complete.

**In parallel: Phase 2 Sprint 2 in plan mode.** PR #11 closed the
cross-quarter recompute item. Remaining Sprint 2 work: per-peer sort,
ratio category collapse/expand, per-ratio drilldown route, restatement
tooltip (per-cell indicator already lights up post-#11; only the hover
surface is missing), conditional formatting heat map, regulatory
threshold amber flags.

The new-chat prompt is at `~/.claude/plans/next-chat-prompt-amber-flag.md`.
Open a fresh Claude Code session, paste the contents, and the session will
enter plan mode and design the Sprint 2 sequencing (which features as which
PRs, in what order, with what test plans) before writing any code. The
prompt predates PR #11 — call out at the top of the new session that
cross-quarter recompute is already merged so the plan doesn't double-count it.

Sprint 2 = Phase 2 DoD complete. After it lands, Phase 4 polish (insights +
Excel export + banking design pass + README/Loom) is the only thing left.

### Then: Phase 4 kickoff

Phase 4 is 2.5 days of polish per `PLAN.md` v1.3:

1. **Insights generation** — `/insight <cert> <quarter>` slash
   command + skill. 3 commentary bullets per peer/quarter pair,
   citing specific schedules (RC-C, RC-K, RC-R).
2. **Excel comp workbook export** — `uv run peerbench export --quarter
   YYYY-Qn --output ./output/`. Reads from the same `ratios` table the
   dashboard uses. Six tabs: Cover, Summary, Comp Sheets, Time Series
   by category, Restatement Log, Methodology. Specs in `PLAN.md` v1.3.
3. **Banking design pass** — tabular-nums everywhere, conditional
   formatting parity with the dashboard, print CSS verified by printing
   Summary + one Comp Sheet drilldown to PDF. The anchor tint `6%`
   hardcoded inline-style P3 cleanup belongs here.
4. **Polish** — README, ARCHITECTURE.md, screenshots, one Loom.

Recommended sub-phase order: Phase 4.2 (Excel export) → Phase 4.3
(design pass) → Phase 4.1 (insights) → Phase 4.4 (polish). Reasoning:
Excel export and design pass are the two highest-signal interview
artifacts; insights generation is more ergonomic if the design pass
has already locked the visual vocabulary.

## Definition of done for Phase 3 (per `PLAN.md` v1.3)

| DoD bullet | State |
| :--- | :--- |
| Production deploy live | ✅ |
| Daily ingest cron green 3 consecutive days | 1 of 3 (calendar wait) |
| Weekly backup cron green ≥ 1 firing | ✅ |
| Sentry receiving events | ✅ (30 server transactions) |
| Dashboard load <1 s | ✅ (warm TTFB 330–600 ms) |
| Restatement markers correct on 5 expected cells | ✅ |

Calendar gate `2026-05-23` + `2026-05-24` is the only remaining bullet.
Once those tick, Phase 3 is DoD-complete.
