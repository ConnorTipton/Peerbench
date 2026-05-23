# Peerbench — handoff (2026-05-22 late night, Sprint 2 PR-A → PR-D + Vitest + design-critic landed)

You are continuing work on Peerbench, Connor's FP&A internship-prep project
at `/Users/connortipton/Projects/Peerbench`. Read `CLAUDE.md` and `PLAN.md`
(v1.3) before doing anything substantive.

## TL;DR

- **Sprint 2 plan locked at `~/.claude/plans/zippy-pondering-volcano.md`.**
  Five atomic PRs in order A → B → C → D → E. Item (g) cross-quarter
  recompute is excluded (already merged via PR #11). Three pre-plan
  design decisions confirmed: shadcn/Radix Tooltip primitive, defer the
  `cre_rbc` 36-month growth gate with a footnote (Phase 4 follow-up to
  ship `cre_rbc_growth_36mo` as a pipeline ratio), 5-atomic-PR chunking.
- **PR #16 (Sprint 2 PR-D) merged at `446a1af`.** Conditional formatting
  heat map + amber/red regulatory flags. Per-ratio quartile cutoffs across
  the visible peer set tint cells `--color-positive` /10 (top quartile) or
  `--color-negative` /10 (bottom), direction-aware via
  `web/lib/heatmap-directions.ts` (e.g. higher NIM = green, higher
  efficiency ratio = red, balance-sheet mix is neutral). Quartile cutoffs
  exclude `data_quality === "suppressed"` cells so a CBLR filer's NULL
  `tier1_rbc` doesn't skew the distribution. Cells crossing thresholds
  defined in `ratio_defs.regulatory_threshold` get amber `/15` (≥amber_pct)
  or red `/20` (≥red_pct); the `△` superscript button opens a Radix tooltip
  with ratio + threshold + citation + the cre_rbc 36-month growth-gate
  footnote. Layer precedence `amber > red > heatmap tint > anchor tint >
  zebra` lives in `composeCellBg` at `ratio-matrix.tsx`. CRE two-tier
  reads from JSONB (added `red_pct: 400` to `data/ratios.csv:26` and
  synced via `peerbench seed-ratios`) — no numeric thresholds hardcoded
  in TS. **Mandatory golden test** landed in `web/lib/heatmap.test.ts`
  (5 values × 3 directions × suppressed-cell fixture, 22 cases). Plus
  `heatmap-directions.test.ts` (7 cases) + `regulatory-thresholds.test.ts`
  (24 cases). New design token `--color-amber: #b45309` (Tailwind amber-700,
  banker-conservative). Codex round 1 GATE PASS, **0 findings** (third
  consecutive PR this Sprint to clear codex on round 1, after PR-C and
  PR #15). Codex verbatim: *"The changes add heat-map bucketing and
  regulatory threshold presentation without introducing an evident
  correctness issue in the modified code. TypeScript checking passes for
  the web package."* Design-critic ran for the first time (sub-agent
  promoted to first-class in this PR; see `.claude/agents/design-critic.md`)
  — 0 blocking, 2 soft issues. One fixed on-branch in commit `3a44b54`
  (added `--text-superscript: 10px` token, converted 3 sites from
  `text-[10px]` to `text-superscript`, formalized in design.md
  §Typography); the other (double `resolveThreshold` call per cell)
  deferred with rationale — negligible at 150-cell scale. Live on prod
  at https://peerbench-web.vercel.app/ — HTTP 200, 538 ms TTFB, 4 amber
  buttons rendered on 2025-Q4 data (cre_rbc @300%, cd_rbc @100%,
  uninsured_dep @50% ×2); all 4 color-mix patterns active.
- **PR #15 (Vitest test runner) merged at `ef4b45c`.** Zero-feature
  setup PR landed ahead of Sprint 2 PR-D so the "mandatory" quartile
  golden test (`computeQuartileCutoffs` + `bucketForCell`) has a runner
  to land into. `vitest@^4.1.7` devDep + minimal `vitest.config.ts`
  (node env, `@/*` alias mirroring tsconfig, `lib/**/*.test.ts` glob);
  `npm test` (one-shot) + `npm run test:watch`. Backfilled 68 golden
  tests across the four pure-helper modules already shipped:
  `lib/collapse.test.ts` (15), `lib/sort.test.ts` (25),
  `lib/format.test.ts` (19), `lib/ratio-order.test.ts` (9). Codex
  round 1 GATE PASS, **0 findings** (second consecutive PR this Sprint
  to clear codex on round 1, after PR #14). Codex also re-ran
  `npx tsc --noEmit` during review (succeeded in 1878ms) so strict
  mode passes against the new test files.
- **PR #14 (Sprint 2 PR-C) merged at `04fcfbd`.** Ratio category
  collapse/expand. Section header rows are now `<button>` click targets
  that toggle visibility of the data rows under that category. URL state
  via `?collapsed=cat1,cat2` (canonical `CATEGORY_ORDER` serialization),
  parsed server-side in `app/page.tsx` so deep links render in the right
  collapsed state with no hydration flicker; client updates via
  `router.replace` + `useTransition`. Pure helpers live in
  `web/lib/collapse.ts` (`parseCollapsedParam`, `serializeCollapsedParam`,
  `toggleCategory`). **Sort + collapse interaction** (design decision
  locked at the start of the chunk): sort runs over ALL data rows
  including hidden ones, so re-expanding a collapsed section shows its
  rows already in the active sort order — no jump or re-sort flicker.
  Collapse is therefore a pure render-time filter applied AFTER
  `sortWithinSections`. Chevron is `▾` (expanded) / `▸` (collapsed) in
  `text-text-tertiary`, button has `aria-expanded` + descriptive
  `aria-label`. Codex round 1 GATE PASS, **0 findings** (first PR-X this
  Sprint to clear codex without a follow-up commit). Live on prod —
  `?collapsed=profitability,yields` returns HTTP 200; `?collapsed=foo`
  (invalid category) gracefully ignored, HTTP 200.
- **PR #13 (Sprint 2 PR-B) merged at `df6d80d`.** Per-peer column sort.
  Clicking a peer column header sorts ratio rows by that peer's value,
  cycling **asc → desc → none**; section dividers act as barriers (sort
  within each category, not globally). URL state via `?sort=cert:dir`
  (e.g. `?sort=4063:desc`), parsed server-side in `app/page.tsx` so deep
  links render in the right order with no hydration flicker; client
  updates via `router.replace` + `useTransition`. Pure helpers live in
  `web/lib/sort.ts`. Two codex P2s caught on first review (back/forward
  nav drift + repeated-key search-param crash) and fixed on the same
  branch via commit `365575d`; round 2 codex GATE PASS, **0 findings**.
  Live on prod — `?sort=4063:asc` returns 1 col ascending / 4 none;
  `?sort=A&sort=B` returns HTTP 200 (no crash on repeated keys).
- **PR #12 (Sprint 2 PR-A) merged at `80d2b58`.** Restatement tooltip
  per `docs/design.md` §Restatement-indicator. Hovering the `r` on any
  restated cell now reveals `LNLSGR: was 1,234,567, now 1,234,890`
  with the detection date and a conditional "values in thousands" suffix
  (omitted for non-dollar fields like `CBLRIND`). Two codex P2s caught
  on first review (a11y + non-dollar field labelling) and fixed on the
  same branch via commit `1edcaab`; round 2 codex GATE PASS, 0 findings.
  Live on prod at https://peerbench-web.vercel.app/ — HTTP 200, 573 ms
  TTFB.
- **PR #11 merged at `a0cfbdd`** (the predecessor Sprint 2 item).
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
- **Test count: 85 pytest + 122 vitest.** Python suite unchanged across
  PR-A through PR-D and PR #15 — none touched the value path. Vitest
  is the first JS test runner in `web/`; suite now covers seven pure-helper
  modules (`collapse.ts`, `sort.ts`, `format.ts`, `ratio-order.ts`,
  `heatmap.ts`, `heatmap-directions.ts`, `regulatory-thresholds.ts`).
  PR #16 contributed 54 new cases across the three heat-map modules.
- **Working tree:** on `main` @ `446a1af`, clean. Feature branches
  `phase-2-cross-quarter-recompute`, `phase-2-restatement-tooltip`,
  `phase-2-per-peer-sort`, `phase-2-category-collapse`,
  `phase-2-web-vitest`, and `phase-2-heatmap-amber-flags` all deleted
  on merge.

## What landed this session (PRs #6, #7, #8, #9, #10, #11, #12, #13, #14, #15, #16)

### PR #16 — Sprint 2 PR-D: conditional formatting heat map + amber/red flags (squash-merge `446a1af`)

Branch `phase-2-heatmap-amber-flags`. Four commits squashed on merge:

1. **`a3dceff` — `feat(web):` heat map helpers + golden tests (chunk 1).**
   CSV edit (cre_rbc `red_pct: 400` added) + `peerbench seed-ratios`
   sync, then three framework-free TS modules + three test files.
2. **`a8720b6` — `feat(web):` heat map + amber/red flag wire-up (chunk 2).**
   `cutoffsByRatio` useMemo, layered `composeCellBg`, `DataCell`
   regulatory flag tooltip threading, `--color-amber` token in @theme,
   design.md updates (opacity tiers, layer precedence, CRE two-tier
   formalization).
3. **`3a44b54` — `fix(web):` design-critic — `--text-superscript` token.**
   In-PR cleanup for the design-critic soft issue: added the token to
   `@theme`, converted 3 sites in `ratio-matrix.tsx` from `text-[10px]`
   to `text-superscript`, documented in design.md §Typography.
4. **`8072ac9` — `chore(.claude):` design-critic sub-agent file.**
   CLAUDE.md had listed `design-critic` as a Phase 2/4 sub-agent but the
   file didn't exist; this commit makes it a first-class agent
   discoverable by Claude Code's agent loader.

**Diff (11 files, +956/-12):**

- `data/ratios.csv` (+1/-1) — `cre_rbc` regulatory_threshold gains
  `red_pct: 400`. Synced to `ratio_defs` via `peerbench seed-ratios`.
- `web/lib/heatmap.ts` (+81, new) — `computeQuartileCutoffs` (Type-7
  quartile, equivalent to Excel QUARTILE.INC / R default) + `bucketForCell`.
  Strict-> boundary semantics; returns null cutoffs when <4 finite values
  (e.g. an all-CBLR peer set queried for tier1_rbc, where the matrix
  falls back to no quartile tint).
- `web/lib/heatmap-directions.ts` (+71, new) — per-ratio direction map
  covering all 30 ratio_ids. Concentration ratios (`cre_rbc`, `cd_rbc`)
  are `neutral` (regulatory-only, no quartile tint). Balance-sheet mix
  is mostly `neutral`. Funding-risk heuristics (`uninsured_dep`,
  `brokered_dep`, `htm_loss_t1`) are `higher_is_negative`. Direction
  defaults to `neutral` for unknown ratio_ids.
- `web/lib/regulatory-thresholds.ts` (+83, new) — resolver reads
  `amber_pct` / `red_pct` from `RatioDef.regulatory_threshold` JSONB;
  no numeric thresholds hardcoded in TS. Citation strings (presentational
  text, no math) live here keyed by ratio_id. `cre_rbc` gets the SR 07-1
  §III.A 36-month growth-gate footnote on every amber/red result. Capital
  ratios (`tier1_rbc`, etc.) carry `min_well_capitalized` but are
  intentionally NOT flagged — that's an informational floor, not a
  concentration-risk amber trigger.
- `web/lib/heatmap.test.ts` (+165, new) — 22 tests including the
  plan-mandated golden case (5 values × 3 directions × suppressed-cell
  exclusion → expected bucket).
- `web/lib/heatmap-directions.test.ts` (+71, new) — 7 tests covering
  the 1:1 correspondence with `RATIO_ORDER`, valid direction enum,
  category-level direction expectations, and `directionFor` lookup
  fallback to `neutral`.
- `web/lib/regulatory-thresholds.test.ts` (+170, new) — 24 tests covering
  cre_rbc two-tier (boundary + above/below), single-tier amber for the
  four other regulatory ratios, capital-floor non-trigger, JSONB
  defensiveness (missing, NaN, non-numeric, no citation), and
  `CRE_GROWTH_GATE_FOOTNOTE` attachment.
- `web/components/ratio-matrix.tsx` (+114/-9) — adds `cutoffsByRatio`
  useMemo (recomputes only when `ratioGroups`, `institutions`, or
  `cells` change), `composeCellBg` helper with the locked layer
  precedence as an explicit if/else cascade, regulatory flag tooltip
  via Radix primitive (reused from PR-A, no new dep), and threading of
  `threshold` + `ratioName` into `DataCell`.
- `web/app/globals.css` (+2) — adds `--color-amber: #b45309` and
  `--text-superscript: 10px` tokens to `@theme`.
- `docs/design.md` (+13/-3) — formalizes `--color-amber`,
  `--text-superscript`, the `/10` `/15` `/20` opacity tiers, layer
  precedence, and the `cre_rbc` two-tier (300 amber / 400 red) with
  growth-gate deferral language.
- `.claude/agents/design-critic.md` (+145, new) — promotes the
  design-critic sub-agent to first-class (CLAUDE.md had listed it; the
  file didn't exist). Hard rules trace directly to design.md §Don'ts +
  §Layout rules; PR-D-specific checklist included for the conditional
  formatting heat map so the agent stays useful through Phase 4.

**Codex round-trip:**

- Round 1 (cumulative across `a3dceff` + `a8720b6`): GATE PASS, **0 findings**
  (third consecutive PR this Sprint to clear codex on round 1, after
  PR-C and PR #15). Codex verbatim: *"The changes add heat-map bucketing
  and regulatory threshold presentation without introducing an evident
  correctness issue in the modified code. TypeScript checking passes
  for the web package."*

**Design-critic round-trip:**

- Round 1 (cumulative across `a3dceff` + `a8720b6`): PASS, 0 blocking,
  2 soft issues.
  - **[Soft-1] `text-[10px]` arbitrary Tailwind size** at three sites
    in `ratio-matrix.tsx` (2 new in PR-D, 1 legacy from PR-A's `r`
    superscript) with no matching `@theme` token. Fixed on-branch in
    commit `3a44b54`: added `--text-superscript: 10px` token, converted
    all three sites, documented in design.md §Typography.
  - **[Soft-2] Double `resolveThreshold` call per cell** (once in
    `composeCellBg`, once in the column cell renderer for the tooltip
    trigger). Negligible at 150-cell scale. Deferred with rationale —
    revisit if PR-E grows the peer count or if the React profiler ever
    flags it as a hot path.

**Verification on merge:** 122/122 vitest pass; 85/85 pytest unchanged.
`npm run lint` 0 errors, 1 warning (pre-existing TanStack memo warning
at `ratio-matrix.tsx:268`, line number shifted from 224 → 266 → 268 as
hooks were added in chunk 2). `npm run build` clean Turbopack compile +
Sentry source-map upload. Vercel rebuild succeeded; prod URL HTTP 200,
**538 ms TTFB**, 4 amber buttons rendered on 2025-Q4 data, all 4
color-mix patterns active (`--color-amber` 15%, `--color-negative` 10%
bottom-quartile, `--color-positive` 10% top-quartile, `--color-primary`
6% anchor).

**Plan-file review report:** logged via `gstack-review-log`; absorbed
into the `## GSTACK REVIEW REPORT` table in
`~/.claude/plans/zippy-pondering-volcano.md` (6 codex runs across
PR-A → PR-D, all CLEAR; 4 findings total, 4/4 fixed; PR-D contributed
0). First entry for `design-critic` row (1 run, 2 soft, 1 fixed,
1 deferred).



### PR #15 — Vitest runner + golden tests for pure helpers (squash-merge `ef4b45c`)

Branch `phase-2-web-vitest`. Single commit `0ea04d3` squashed on merge —
no codex follow-up commits this round (second consecutive PR this Sprint
to clear codex on round 1, after PR #14).

**Why this 0-feature PR.** Sprint 2 PR-D (heat map + amber flags) requires
a **mandatory** golden test on `computeQuartileCutoffs` + `bucketForCell`
per `~/.claude/plans/zippy-pondering-volcano.md` lines 213-216 (the quartile
math is brittle to silent direction flips). PRs A/B/C each deferred their
unit tests for lack of a runner; this PR closes that infra gap once and
backfills coverage on the four pure-helper modules already shipped, so
PR-D can ship tested in the established `lib/X.test.ts` pattern.

**Diff (7 files, +1281/-5):**

- `web/package.json` (+2 scripts, +1 devDep) — adds `vitest@^4.1.7` as a
  devDependency plus `npm test` (one-shot: `vitest run`) and
  `npm run test:watch` (TDD loop: `vitest`) scripts.
- `web/package-lock.json` (+779/-3) — vitest dep tree (vite, rollup,
  picocolors, etc., all dev-only).
- `web/vitest.config.ts` (+14, new) — minimal config: `environment: "node"`
  (no DOM needed for these helpers), `include: ["lib/**/*.test.ts"]` glob,
  manual `@/*` alias to `./` mirroring tsconfig.json. No `vite-tsconfig-paths`
  dep added — manual alias keeps the dep footprint single-line.
- `web/lib/collapse.test.ts` (+118, new) — 15 tests. Covers
  `parseCollapsedParam` (undefined / empty / single / multi / unknown-slug
  defense / empty-segment / dedupe), `serializeCollapsedParam` (empty → null,
  canonical CATEGORY_ORDER independent of insertion order, round-trip with
  `parseCollapsedParam`), `toggleCategory` (add / remove / immutability /
  other-entry preservation), and `CATEGORY_ORDER` invariants.
- `web/lib/sort.test.ts` (+218, new) — 25 tests. Covers
  `parseSortParam` (10 cases incl. valid asc/desc, unknown cert, bad dir,
  malformed input, non-numeric cert, missing parts), `serializeSortParam`
  (null + round-trip), `nextSortState` (4 cycle states), `compareValues`
  (nulls-always-last in both directions), and `sortWithinSections`
  (7 cases: section barriers, asc/desc within sections, nulls-last
  invariant, stable-sort preservation, empty section, empty list, buffer
  flush for data rows before any section).
- `web/lib/format.test.ts` (+80, new) — 19 tests. Covers `formatRatio`
  (null/undefined/NaN/Infinity → em-dash; positive → percent; zero → 0.00%;
  parentheses-negatives, no minus signs per `docs/design.md`;
  two-decimal rounding), `formatFactValue` (US thousands separator,
  parentheses-negatives, fractional rounding to whole numbers), and
  `formatReportDate` (ISO date passthrough; timestamp trimmed to date).
- `web/lib/ratio-order.test.ts` (+57, new) — 9 tests. Asserts
  `CATEGORY_ORDER` is exactly the 7 analyst-facing categories in the
  specified order, `CATEGORY_LABELS` is 1:1 with `CATEGORY_ORDER`,
  `RATIO_ORDER` has 30 entries with no duplicates and uses post-CECL
  `acl_*` (never `alll_*`).

**Codex round-trip:**

- Round 1 (`0ea04d3`): GATE PASS, **0 findings**. Codex verbatim:
  *"The branch only adds Vitest setup and unit tests for existing pure
  helpers. I did not find any discrete regression or configuration issue
  in the changed files."* Codex additionally ran `npx tsc --noEmit`
  against `web/` during review (succeeded in 1878ms) so strict mode
  type-checks the new test files cleanly.

**Verification on merge:** 68/68 vitest pass (cold ~220ms). 85/85 pytest
unchanged. `npm run lint` 0 errors, 1 warning (pre-existing TanStack memo
warning at `ratio-matrix.tsx:224`). `npm run build` clean Turbopack
compile + Sentry source-map upload. No runtime behavior change; no
dashboard route touched; no Vercel env vars affected.

**Out of scope (intentional):**

- jsdom / React component testing — helpers are framework-free; add
  `jsdom` only when a component test is needed (e.g. `ratio-matrix.tsx`
  interactions).
- `lib/queries.ts` / `lib/supabase.ts` — Supabase-bound, not pure;
  testing requires either a mock client or a hermetic test DB. Out of
  scope for a setup PR.



### PR #14 — Sprint 2 PR-C: ratio category collapse/expand (squash-merge `04fcfbd`)

Branch `phase-2-category-collapse`. Single commit `3e6a58d` squashed on
merge — no codex follow-up commits this round (first PR-X this Sprint to
clear codex on round 1).

**Diff (4 files, +158/-7):**

- `web/lib/collapse.ts` (+56, new) — pure helpers + canonical-order
  serializer. `parseCollapsedParam` validates against
  `CATEGORY_ORDER` and silently drops unknown slugs (defensive against
  URL hand-edits). `serializeCollapsedParam` joins in `CATEGORY_ORDER`
  so URLs are stable regardless of toggle order. `toggleCategory`
  returns a new `Set` (immutable update).
- `web/components/ratio-matrix.tsx` (+94/-3) — adds `collapsed` state
  via `useState(initialCollapsed)` + URL sync via `router.replace` /
  `useTransition` (mirrors the sort plumbing landed in PR-B). `useEffect`
  resyncs local state when server-derived `initialCollapsed` changes on
  back/forward nav, compared by canonical-string serialization so a
  referentially-new `Set` with identical members is a no-op (avoids the
  PR-B P2-A failure mode). New `visibleRows` `useMemo` filters
  `sortedRows` after sort — section rows always render; data rows hidden
  if their `r.def.category` is in the `collapsed` set. New
  `SectionToggle` component renders the section row as a `<button
  type="button">` inside the existing `<td colSpan>` (padding moved from
  td to button so the entire row is the hit target); `aria-expanded` +
  descriptive `aria-label`; chevron `▾` / `▸` in `text-text-tertiary`
  per design token; focus ring matches `SortHeader` and tooltip trigger.
- `web/app/page.tsx` (+12/-1) — `SearchParams` gains `collapsed?: string
  | string[]`; `firstParam(collapsed)` normalizes (the PR-B P2-B
  hardening pattern); threaded as `initialCollapsed` to
  `<RatioMatrix>`. Hydration-safe.
- `web/components/anchor-select.tsx` (+3, comment-only) — three-line
  comment documenting the `URLSearchParams` copy-then-set pattern that
  `ratio-matrix.tsx` reuses. Plan called this out so future authors can
  find prior art.

**Codex round-trip:**

- Round 1 (`3e6a58d`): GATE PASS, **0 findings**. Codex verbatim: *"No
  correctness issues were found in the reviewed diff. The collapse
  state parsing, URL synchronization, and row filtering appear
  consistent with the existing sort behavior."*

**Verification on merge:** 85/85 tests pass. `npm run lint` 0 errors,
1 warning (pre-existing TanStack memo warning at `ratio-matrix.tsx:224`,
line number shifted from 174 → 224 as the new hooks were added).
`npm run build` clean Turbopack compile + Sentry source-map upload.
Vercel rebuild succeeded; prod URL HTTP 200 on `/`,
`/?collapsed=profitability,yields`, and `/?collapsed=foo` (invalid
category, gracefully ignored). Cold TTFB 286 ms.

**Plan-file review report:** logged via `gstack-review-log`; absorbed
into the `## GSTACK REVIEW REPORT` table in
`~/.claude/plans/zippy-pondering-volcano.md` (5 codex runs across
PR-A → PR-C, all CLEAR; 4 findings total, 4/4 fixed; PR-C contributed 0).



### PR #13 — Sprint 2 PR-B: per-peer column sort (squash-merge `df6d80d`)

Branch `phase-2-per-peer-sort`. Two commits squashed on merge:

1. **`6e70261` — `feat(web):` per-peer column sort.** Implements the
   Sprint 2 PR-B item from `~/.claude/plans/zippy-pondering-volcano.md`.
   Sort cycle on the active column is **asc → desc → none**; section
   dividers act as barriers (sort within each category, not globally).
   New pure-helpers module at `web/lib/sort.ts` (`parseSortParam`,
   `serializeSortParam`, `nextSortState`, `compareValues`,
   `sortWithinSections`) — framework-free and ready for unit tests when
   a JS test runner lands in `web/`.
2. **`365575d` — `fix(web):` codex P2 — URL→state sync + repeated-key
   search-param hardening.** In-PR fixup for both P2s codex flagged on
   commit `6e70261`.

**Diff (3 files, +218/-12):**

- `web/lib/sort.ts` (+85, new) — pure helpers + section-aware
  partitioner. Null-valued cells (suppressed / missing) always sort to
  the bottom regardless of direction so blanks never masquerade as 0
  or huge. Stable sort guaranteed (ES2019+) so equal compare values
  preserve input order.
- `web/components/ratio-matrix.tsx` (+123/-9) — sort state via
  `useState(initialSort)` + URL sync via `router.replace` /
  `useTransition` (matches the existing `?anchor=` pattern in
  `anchor-select.tsx`). `useEffect` resyncs local sort when the
  server-derived `initialSort` actually changes (back/forward nav
  case), compared by primitive cert/dir to avoid re-fires on
  referentially-new-but-equal SortState objects. New `SortHeader`
  component renders the header as a `<button>` with an `aria-label`
  and a unicode chevron (`↑` / `↓` / `↕`); `aria-sort` lives on the
  `<th>` per spec, with values `"ascending"` / `"descending"` /
  `"none"` keyed on the column's `meta.cert`. Focus ring is
  `focus-visible:outline-1 focus-visible:outline-accent` per
  `docs/design.md` "single accent color for focus rings".
- `web/app/page.tsx` (+15/-3) — server-side `?sort=` parse, threaded
  as `initialSort` into `<RatioMatrix>` to avoid hydration flicker.
  `SearchParams` type now acknowledges `string | string[]` (Next.js
  represents repeated query-string keys as arrays at runtime), and a
  `firstParam()` boundary normalizer is applied to both `sort` and
  `anchor` before parsing. Downstream parsers in `lib/sort.ts` stay
  pure (`string | undefined` in).

**Codex round-trip:**

- Round 1 (`6e70261`): GATE PASS (0 P1, 2 P2).
  - **[P2-A]** `useState(initialSort)` only runs on mount, so when
    the URL changed via back/forward nav (or any other route that
    rewrote `?sort=`), the client component kept its stale local
    sort and the table diverged from the URL bar. Fixed by adding a
    `useEffect` that resyncs `sort` when the server-derived
    `initialSort` changes, compared by primitive cert/dir.
  - **[P2-B]** Next.js represents repeated query-string keys as
    `string[]` at runtime even when the TypeScript narrows to
    `string`. A URL like `?sort=4063:asc&sort=4214:desc` would have
    hit `raw.split(":")` on an array and 500'd the page. Fixed by
    updating `SearchParams` to `string | string[]` and adding
    `firstParam()` at the boundary.
- Round 2 (`365575d`): GATE PASS, **0 findings**. Codex verbatim:
  *"The URL parameter normalization covers the expected Next.js
  string, string array, missing, and empty-value shapes. The sort
  resync effect compares primitive fields before updating state and
  does not create an update loop, while the optimistic sort update
  is not immediately overwritten by unchanged props."*

**Verification on merge:** 85/85 tests pass. `npm run lint` 0 errors,
1 warning (the same pre-existing TanStack memo warning at
`ratio-matrix.tsx:174`). `npm run build` clean Turbopack compile.
Vercel rebuild succeeded; prod URL HTTP 200 on both
`/?sort=4063:asc` (aria-sort=`ascending` on the MidFirst col, `none`
on the other four) and `/?sort=A&sort=B` (HTTP 200, no crash on
repeated keys). Warm TTFB 1.4 s on first hit (cold cache after
deploy); previously banked warm TTFB 330-600 ms held.



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

### PR #12 — Sprint 2 PR-A: restatement tooltip (squash-merge `80d2b58`)

Branch `phase-2-restatement-tooltip`. Two commits squashed on merge:

1. **`581750b` — `feat(web):` restatement tooltip on `r` superscript.**
   Closes the `docs/design.md` §Restatement-indicator hover surface that
   was specced but never implemented (previous behavior was a static
   `title=` attribute). Hovering the `r` on any restated cell now reveals
   `"Was X, now Y"` with the detection date.
2. **`1edcaab` — `fix(web):` codex P2 — a11y + non-dollar field labelling.**
   In-PR fixup for the two P2s codex flagged on commit `581750b`.

**Diff (9 files, +622/-26):**

- `web/components/ui/tooltip.tsx` (new) — thin styled wrapper around
  `@radix-ui/react-tooltip`. Hand-written, not `npx shadcn add tooltip`,
  because `shadcn init` would overwrite the existing `@theme` palette in
  `app/globals.css`. Functionally equivalent; design tokens remain the
  source of truth.
- `web/app/layout.tsx` — mounts `<TooltipProvider delayDuration={150}>`
  once at the root so all tooltips share state.
- `web/lib/queries.ts` — `restatedKeys: Set<string>` →
  `restatedDetails: Map<string, RestatedDetail>`. Same single round-trip
  to `quality_log` (`old_value` / `new_value` / `detected_at` / `field_code`
  were already SELECTed); now serialized into the Map instead of dropped.
  Documented the multi-field-per-ratio overwrite caveat — benign for the
  5 known restatements in current production data.
- `web/lib/matrix-types.ts` — exports `RestatedDetail` type with
  `field_code`, `old_value`, `new_value`, `detected_at`.
- `web/lib/format.ts` — new `formatFactValue()` helper. The cell renders
  the ratio percentage via `formatRatio()`; the tooltip renders the
  underlying raw FFIEC field amounts via `formatFactValue()` (thousands-
  separated integers, parentheses-negatives). The plan said to reuse
  `formatRatio()` but `quality_log.old_value/new_value` are raw field-
  level dollar amounts, not ratios.
- `web/components/ratio-matrix.tsx` — threads `restatedDetails` through
  the cell render path; wraps the `r` indicator in `<Tooltip>` and renders
  a `RestatementTooltipBody` showing `LNLSGR: was X, now Y` (field code
  leads). Trigger is `<button type="button">` with `align-super text-[10px]`
  to keep the superscript appearance while remaining keyboard-focusable;
  `focus-visible:outline-1 focus-visible:outline-accent` per
  `docs/design.md` "single accent color for focus rings". A
  `NON_DOLLAR_FIELDS = new Set(["CBLRIND"])` allowlist suppresses the
  "values in thousands" suffix for flag fields.
- `web/app/page.tsx` — passes `data.restatedDetails` instead of
  `data.restatedKeys`.
- `web/package.json` + `web/package-lock.json` — adds
  `@radix-ui/react-tooltip` (~13 KB gzipped).

**Codex round-trip:**

- Round 1 (`581750b`): GATE PASS (0 P1, 2 P2).
  - **[P2-A]** `<sup>` trigger isn't keyboard-focusable → Radix never opens
    on `Tab` focus. Tooltip was pointer-only.
  - **[P2-B]** Hard-coded "values in thousands" suffix mislabelled
    `CBLRIND` (a 0/1 suppression flag already in the field-dep graph).
- Round 2 (`1edcaab`): GATE PASS, **0 findings**. Codex verbatim: *"The
  prior accessibility and non-dollar labeling issues appear addressed:
  the restatement marker is focusable via a button/tooltip trigger, and
  CBLRIND no longer receives the thousands label. I found no blocking
  correctness issues in the branch diff."*

**Verification on merge:** 85/85 tests pass. `npm run lint` 0 errors,
1 warning (pre-existing TanStack memo warning at `ratio-matrix.tsx:115`).
`npm run build` clean Turbopack compile + Sentry source-map upload.
Vercel rebuild succeeded; prod URL HTTP 200, **573 ms TTFB**
(well under the <1 s DoD target).

**Plan-file review report:** logged via `gstack-review-log`; appended as
`## GSTACK REVIEW REPORT` to `~/.claude/plans/zippy-pondering-volcano.md`.

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

### Phase 2 — Sprint 2 (in flight)

Sprint 2 plan locked at `~/.claude/plans/zippy-pondering-volcano.md`.
Five atomic PRs in order A → B → C → D → E. PR-A through PR-D have all
landed; only PR-E remains. Cross-quarter recompute (originally item g)
already merged via PR #11 and is excluded from the plan. The JS
test-runner infrastructure called out as a PR-D pre-req shipped as
PR #15 (out-of-band 0-feature setup PR).

- ~~**PR-A** Restatement tooltip~~ **Closed by PR #12 @ `80d2b58`.**
  Hover on `r` superscript reveals "Was X, now Y (restated YYYY-MM-DD)"
  with field code and conditional "values in thousands" suffix. Two
  codex P2s caught and fixed on the same branch (commit `1edcaab`).
- ~~**PR-B** Per-peer column sort~~ **Closed by PR #13 @ `df6d80d`.**
  Header-click cycle asc → desc → none, sort scoped within each
  category section (sections act as barriers, not pinned dividers —
  the plan's "anchor row pinning" language didn't match the data
  model; rows are ratios, columns are peers). Pure-helpers module at
  `web/lib/sort.ts`. Two codex P2s caught and fixed on the same
  branch (commit `365575d`): URL-change resync via `useEffect` keyed
  on primitive cert/dir, and `string | string[]` boundary
  normalization in `app/page.tsx`.
- ~~**PR-C** Ratio category collapse/expand~~ **Closed by PR #14 @
  `04fcfbd`.** Section header rows are `<button>` toggles with
  `aria-expanded` + chevron (`▾` / `▸`); URL state via
  `?collapsed=cat1,cat2`; server-side parse in `app/page.tsx`. Sort
  runs over ALL rows so re-expanding a collapsed section shows its
  rows already in the active sort order (locked design choice).
  Pure helpers in `web/lib/collapse.ts`. Codex round 1 GATE PASS, 0
  findings (first PR-X this Sprint to clear codex on round 1).
- ~~**PR-D** Conditional formatting heat map~~ **Closed by PR #16 @
  `446a1af`.** Three pure-helper modules + 54 golden tests; layered
  `composeCellBg` with the locked precedence `amber > red > heatmap
  tint > anchor tint > zebra`. `cre_rbc` two-tier (300/400) reads from
  the same JSONB as every other threshold (added `red_pct: 400` to
  `data/ratios.csv:26` and synced). `cre_rbc` 36-month growth gate
  deferred to Phase 4 with a tooltip footnote. Codex round 1 GATE PASS,
  0 findings. Design-critic ran for the first time (newly-minted
  first-class sub-agent in `.claude/agents/design-critic.md`); 0
  blocking, 2 soft — one fixed on-branch (`text-[10px]` →
  `--text-superscript` token, commit `3a44b54`), one deferred (double
  `resolveThreshold` call, negligible at 150 cells).
- **PR-E** Per-ratio drilldown at `/ratio/[ratio_id]`. 8-quarter
  Recharts `LineChart` + ScatterChart strip plot (not box plot — N=5
  peers is statistically thin). Add `recharts` (~90 KB gzipped) only to
  this route's bundle.

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
#   <new HANDOFF commit>  docs(handoff): post-PR-#16 — Sprint 2 PR-D landed
#   446a1af  feat(web): conditional formatting heat map + amber/red flags (Sprint 2 PR-D) (#16)
#   384b339  docs(handoff): post-PR-#15 — Vitest landed, PR-D unblocked
#   ef4b45c  chore(web): add Vitest runner + golden tests for pure helpers (#15)
#   38e2e4d  docs(handoff): post-PR-#14 — Sprint 2 PR-C landed
#   04fcfbd  feat(web): ratio category collapse/expand (Sprint 2 PR-C) (#14)
#   37818f2  docs(handoff): post-PR-#13 — Sprint 2 PR-B landed
#   df6d80d  feat(web): per-peer column sort (Sprint 2 PR-B) (#13)
#   2e5dbc7  docs(handoff): post-PR-#12 — Sprint 2 PR-A landed
#   80d2b58  feat(web): restatement tooltip on `r` superscript (Sprint 2 PR-A) (#12)

cd /Users/connortipton/Projects/Peerbench && uv run pytest 2>&1 | tail -3
# Expect: 85 passed

cd web && npm test 2>&1 | tail -5
# Expect: Test Files 7 passed (7), Tests 122 passed (122).

cd web && npm run lint 2>&1 | tail -3
# Expect: 0 errors, 1 warning (pre-existing TanStack memo warning at ratio-matrix.tsx:268).

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
uv run pytest                                       # 85 tests
uv run peerbench info                               # 30 handlers, 65 field codes
uv run peerbench ingest --cert 4063 --quarters 1    # FDIC API
uv run peerbench compute --cert 4063 --quarters 1   # compute ratios
uv run peerbench validate --certs 4063 --quarters 1 # bp diff vs FDIC precomputed
uv run peerbench export-field-deps                  # regenerate handler→field snapshot

# Dashboard (local)
cd web && npm install && npm run dev                # http://localhost:3000
cd web && npm test                                  # 68 vitest unit tests (one-shot)
cd web && npm run test:watch                        # vitest TDD loop

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

**Active: Phase 2 Sprint 2 PR-E (per-ratio drilldown).** The Sprint 2
plan is locked at `~/.claude/plans/zippy-pondering-volcano.md`. PR-A
through PR-D have all landed (#12 / #13 / #14 / #16), with PR #15 in
between to ship the Vitest infra. **PR-E is the last Sprint 2 item;
once it lands, Phase 2 DoD is closed and Phase 4 starts.**

PR-E scope (from the plan, lines 234+):

- New route at `/ratio/[ratio_id]` — server-rendered drilldown for a
  single ratio across all peers + 8 quarters of history.
- 8-quarter trend chart (`Recharts` `LineChart`, one line per peer with
  the anchor highlighted). Add `recharts@^2` (~90 KB gzipped) to
  dependencies. **Make sure `next build` confirms `recharts` is bundled
  only into the `/ratio/[id]` chunk, not the matrix page** — Recharts
  is the only PR-E runtime dependency add, and matrix-page bundle
  bloat would regress the <1s DoD target.
- Strip plot via Recharts `ScatterChart` (not box plot — N=5 peers is
  statistically thin; a box plot's quartile box is meaningless with 5
  observations).
- Link from each ratio name in the matrix `<a href={'/ratio/' + ratio_id}>`
  (or `Link` with prefetch). Server-render the drilldown to keep TTFB
  in the same band as the matrix page.
- Re-use the existing pure helpers where applicable. New per-ratio
  data query in `web/lib/queries.ts` for the 8-quarter × 5-peer cross-
  section. No new pipeline changes — drilldown reads the same `ratios`
  table.

Branch `phase-2-ratio-drilldown` (or similar). Same flow as PR-D:
implement helpers + page + tests, local verify (`npm test` + build +
lint + pytest), push, open PR, `/codex review` + `design-critic` in
parallel, fix any P1/P2s on-branch, squash-merge. Heavy visual diff
(charts) → design-critic is high-value here too.

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
| Dashboard load <1 s | ✅ (warm TTFB 330–600 ms; PR-D rebuild measured 538 ms) |
| Restatement markers correct on 5 expected cells | ✅ |

Calendar gate `2026-05-23` + `2026-05-24` is the only remaining bullet.
Once those tick, Phase 3 is DoD-complete.
