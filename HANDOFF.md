# Peerbench — handoff (2026-05-22 evening, Phase 3 closed end-to-end on prod)

You are continuing work on Peerbench, Connor's FP&A internship-prep project
at `/Users/connortipton/Projects/Peerbench`. Read `CLAUDE.md` and `PLAN.md`
(v1.3) before doing anything substantive.

## TL;DR

- **Phase 3 fully closed in production.** Three PRs squash-merged today
  (2026-05-22) on top of the plumbing landed yesterday:
  - **PR #6 @ `75e5205`** — Vercel deploy + Sentry. Hand-configured Sentry on
    Next.js 16 + Turbopack (`@sentry/nextjs@10.53.1`), v8+ layout
    (`instrumentation.ts` + `instrumentation-client.ts` +
    `sentry.{server,edge}.config.ts` + `app/global-error.tsx`).
    `withSentryConfig` wrap; source-map upload conditional on
    `SENTRY_AUTH_TOKEN`. Codex review PASS, 0 findings.
  - **PR #7 @ `7f177d2`** — sticky table header + first column fix
    (Phase 2 Sprint 1 DoD bug, pre-existing on main since PR #1). 3-line
    diff: `<main>` is now `flex h-screen flex-col`, matrix wrapper is
    `flex-1 overflow-auto`, table is `border-separate border-spacing-0`.
  - **PR #8 @ `eac9f16`** — Sentry tunnel route (`/monitoring`) to bypass
    ad blockers. 3-line diff to `next.config.ts`.
- **PR #9 is OPEN, awaiting codex review** — `actions/checkout` v4 → v6.0.2
  (Node 24 native, ahead of GitHub's 2026-06-02 Node-runtime force-bump).
  2-line diff to `.github/workflows/{daily-ingest,weekly-backup}.yml`.
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
- **Test count: 78 passing** — unchanged this session (no value-path code
  touched).
- **Working tree:** on `main` @ `eac9f16` (will move forward after the
  HANDOFF commit and again after PR #9 merges), clean.

## What landed this session (PRs #6, #7, #8)

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

## PR #9 — actions/checkout v4 → v6 (OPEN, awaiting codex review)

Branch `chore-actions-checkout-node24`. Single commit `bfcb601`.

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
behavior) have zero blast radius.

## Open items / state of play

### Phase 1 — fully closed

- 29 of 30 ratios at `ok` across the 5×8 grid. `top_loan_cat` is
  `partial` (raises `NotImplementedError` — intentional defer to Phase 4).
- Restatement detector wired; produces audit-trail rows on every ingest.

### Phase 2 — Sprint 1 closed

- Dashboard renders the 30-ratio × 5-peer matrix for the latest renderable
  quarter (2025-Q4). Real institution names, anchor tint on MidFirst column,
  **sticky header + first column now actually sticky on scroll (PR #7)**,
  design tokens from `docs/design.md` encoded in Tailwind v4 `@theme`.
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
  remains.
- Cross-quarter recompute for `f.avg(...)` consumers (codex P2 from PR #1).
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
- **PR #9 (actions/checkout v6 bump):** OPEN. Awaiting codex review.
  Trivial diff but the SHA-pin verification is the kind of thing a
  generic codex review catches well.

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
- SQL migrations, GH Actions workflows (until PR #9 lands the
  checkout bump).

## Quick verify (run when picking up the session)

```bash
git -C /Users/connortipton/Projects/Peerbench log main -8 --oneline
# Expect (top to bottom):
#   <new HANDOFF commit>  docs(handoff): post-PR-#8 — Phase 3 closed on prod, PR #9 open
#   eac9f16  feat(web): proxy Sentry events through /monitoring tunnel
#   7f177d2  fix(web): sticky table header + first column on scroll
#   75e5205  Phase 3 — Vercel deploy + Sentry
#   dae4ba0  docs(handoff): post-PR-#5 — Phase 3 plumbing closed end-to-end
#   4abac07  fix(cron): prepend pg17 bin dir to PATH after install (#5)
#   bc208e8  fix(cron): bump weekly-backup pg_dump client 15 → 17 (#4)
#   6f4385c  Phase 3 — RLS + daily cron + weekly backup + runbook (#3)

cd /Users/connortipton/Projects/Peerbench && uv run pytest 2>&1 | tail -3
# Expect: 78 passed

cd web && npm run build 2>&1 | tail -8
# Expect: clean Turbopack compile. If SENTRY_AUTH_TOKEN is set,
# runAfterProductionCompile takes ~7-9s (source-map upload). Otherwise
# it takes <500ms (upload skipped).

gh run list --workflow=daily-ingest.yml --limit 5
# Expect: today's 06:48 UTC scheduled run = success; tomorrow + the
# day after should add two more green entries (~03:00 UTC each).

gh pr view 9 --json state,mergeable
# Expect: OPEN, MERGEABLE. Codex review still owed.

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
- **Sticky table layout (PR #7).** `app/page.tsx`'s `<main>` is
  `flex h-screen flex-col`; the matrix wrapper inside
  `RatioMatrix` is `flex-1 overflow-auto`; the `<table>` uses
  `border-separate border-spacing-0`. Don't refactor any of these
  three pieces in isolation; sticky behavior depends on all three.

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

**PR #9 codex review + merge.** The diff is trivial (2 lines, both
identical SHA pins), but it's a supply-chain-relevant change (every
CI run will execute the bumped commit) so the codex review is worth
running. The custom prompt to paste into a fresh chat is in
`docs/codex-prompts/pr-9-checkout-v6.md` (see below — or use the
inline prompt the user paged into the next chat).

After PR #9 merges:
1. Squash-merge with subject `chore(ci): bump actions/checkout v4 → v6.0.2 (Node 24 native)`.
2. `gh workflow run daily-ingest.yml --ref main` to smoke the new
   checkout pin live (~4 min); confirm green.
3. Calendar wait for `2026-05-23` + `2026-05-24` scheduled cron firings.
   Once both are green, the Phase 3 DoD bullet "daily ingest cron green
   for 3 consecutive days" formally ticks.

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
   formatting on all data tables, print CSS verified by printing
   Summary + one Comp Sheet drilldown to PDF.
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
