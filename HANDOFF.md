# Peerbench — handoff (2026-05-20, Sprint 1 dashboard up; CDR fix queued)

You are continuing work on Peerbench, Connor's FP&A internship-prep project at `/Users/connortipton/Projects/Peerbench`. Read `CLAUDE.md` and `PLAN.md` (v1.3) for the project plan and conventions before doing anything substantive.

## TL;DR

- **Phase 2 Sprint 1 (dashboard) is implemented, smoke-passed locally, and lives in PR #1** (https://github.com/ConnorTipton/Peerbench/pull/1) on branch `phase-2-sprint-1-dashboard-scaffold`. 3 commits, marked ready for review, **not yet merged**. Renders the 30-ratio × 5-peer matrix for the latest renderable quarter (2025-Q4). Confirmed working with real data: real bank names, restatement marker on MidFirst Q4 NIM cell, sticky header + first column, anchor highlight on the MidFirst column, design tokens encoded in Tailwind v4 `@theme`.
- **Sprint 1's two reviewer-flagged soft items are fixed in commit `230bd41`:** arbitrary-value escapes (`text-[length:...]`) replaced with Tailwind v4 utility classes, anchor-column detection moved from positional `institutions[i-1]?.cert` to typed `ColumnMeta.cert` via TanStack module augmentation.
- **Ghost-quarter bug fixed in commit `35165e2`:** `web/lib/queries.ts` was picking latest quarter via `quarters.report_date`, which selects the empty 2026-Q1 ghost row. Now sources latest from `ratios.quarter_id` so the page anchors on the latest *renderable* quarter, not the latest *known* one.
- **CDR ingest ran end-to-end** and surfaced two real bugs (see "Open issues" below). 40 CDR fact rows are now in `facts` (4 banks × 8 quarters × 2 fields) — but the `CDR_CET1_CAPITAL` values are actually **Tier 1 capital amounts** (wrong MDRM), not CET1. Validation gate **FAILS** at mean 19.82 bps / max 82.47 bps for `cet1`. Fix is well-scoped (~45 min) and queued.
- **Working tree as of this handoff:** on branch `phase-2-sprint-1-dashboard-scaffold`. Clean (no uncommitted changes). Local matches `origin/phase-2-sprint-1-dashboard-scaffold` at commit `230bd41`. `main` is still at `b0ea287` until PR #1 lands.
- **63 tests still passing.**

## What landed today (2026-05-20, 3 PR commits)

PR #1 = `phase-2-sprint-1-dashboard-scaffold` branch:

1. **`7317ca0` — feat(web): Phase 2 Sprint 1 — Next.js 16 scaffold + ratio matrix.** Built by Ultraplan in a remote sandbox; pushed to `origin` after the user paired the sandbox to GitHub. Files: `web/` subdir (app/, components/, lib/, types/), package.json/lock, eslint+postcss+tsconfig, README web section, .gitignore additions. Reviewer caught the `Intl.NumberFormat` `style:"percent"` × `currencySign:"accounting"` silent-ignore bug pre-commit; fixed in-place. Single commit by Claude, unsigned (sandbox GPG server returned HTTP 400). Authorship: `Claude <noreply@anthropic.com>` — honest attribution, not a bug.
2. **`35165e2` — fix(web): anchor latest quarter on ratios, seed institution names.** Two real follow-ups surfaced during smoke: (a) the ghost-quarter bug above; (b) institutions table had placeholder `CERT 4063` names; added `sql/seed_institution_names.sql` and applied via Supabase SQL editor. All 5 banks now show real names.
3. **`230bd41` — refactor(web): utility classes + column-meta anchor detection.** The two Sprint 1 reviewer soft items. No visual change — `@theme` tokens map 1:1 to utility classes. Anchor detection no longer positional, so Sprint 2's planned per-peer sort won't break it.

## What also happened today (no commits, infrastructure / data)

- **Supabase RLS pre-flight ran via MCP.** `anon` already has SELECT on `institutions`, `quarters`, `ratio_defs`, `ratios`, `facts`, `quality_log`. RLS is disabled. The Supabase advisor flags `rls_disabled` as critical — fine for Phase 2 dev (public FFIEC data) but Phase 3 production deploy should `ENABLE ROW LEVEL SECURITY` + add a permissive read policy.
- **Institution names updated.** Real names + charter codes for all 5 banks via `sql/seed_institution_names.sql`. Verified.
- **Stale empty `package-lock.json` at repo root deleted** — predated Sprint 1; was misdirecting Next.js workspace root detection.
- **8 CDR ZIPs staged + 9th (2026-Q1) extra in `cache/cdr/`.** `2024-Q1` through `2025-Q4` for the gate; `2026-Q1` won't be used until late June. All contain the expected `RCRI` and `RCB` schedules. Files are gitignored.
- **Live CDR ingest + compute + validate ran.** Findings below.

## Open issues — CDR ingest data quality (queued, see "Recommendation")

The first live CDR ingest surfaced **two separate bugs** that together cause the validation gate to FAIL at mean 19.82 bps / max 82.47 bps on `cet1`. Both have clean root causes; the fix is well-scoped to `src/peerbench/ingest/cdr_schema.py` + `src/peerbench/ingest/cdr.py`.

### Bug 1: Wrong MDRM for CET1 capital

`cdr_schema.py:_STABLE["CET1_CAPITAL"]` is pinned to `RCOA8274`, which is the **legacy Tier 1 capital amount**, not the post-CECL CET1 capital amount. For 3 of 4 matched banks (MidFirst, BOK, Frost), `CET1 == Tier 1` because they have no Additional Tier 1 instruments, so the value happens to be right. **Bank OZK has AT1 preferred stock**, so its CET1 < Tier 1 → 82 bps drift exposed.

**Right MDRM is `P859`.** Verified by extracting the actual TSV header and comparing column values against FDIC's pre-computed `IDT1CER`:

| cert | RCOA8274 (current) | **RCOAP859** | RCFAP859 | FDIC IDT1CER% | Match |
| ---: | ---: | ---: | ---: | ---: | --- |
| 4063 (MidFirst) | 18.53% | 18.53% | — | 18.53% | both |
| 4214 (BOK) | 12.02% | 12.02% | — | 12.02% | both |
| 5510 (Frost) | 14.33% | 14.33% | — | 14.33% | both |
| 110 (Bank OZK) | **12.50% ❌** | 11.72% | — | 11.72% | **P859 only** |
| 11063 (First-Citizens) | — | — | **12.55%** | 12.55% | **RCFAP859 only** |

### Bug 2: Domain prefix split (RCOA vs RCFA)

Domestic-only filers report under `RCOAP859`. Banks with foreign offices (e.g., First-Citizens) report under `RCFAP859`. The current pinning is a single column; First-Citizens shows `0 matched / N scanned` because the column we look at is empty for them.

**Right fix:** make `_STABLE` map to a *tuple of candidate columns*; the ingest tries each in order and takes the first non-empty value per row. Need to update `cdr_column()` return type, the `required_columns` enforcement in `iter_schedule_rows()` (codex P2 fix expects single column name), and ~2 tests.

### Bug 3: RCB multi-file split (HTM data missing for 4 of 5 banks)

FFIEC ships RC-B for 2025-Q4 as **two files**: `FFIEC CDR Call Schedule RCB 12312025(1 of 2).txt` (~1.7 MB) + `(2 of 2).txt` (~0.5 MB). `peerbench.ingest.cdr._find_member` matches the first file and logs `Multiple files match 'RCB' — picking first`. HTM Memorandum 2(d) (MDRM `RCFD1773`) is row-split across the files — only First-Citizens (11063) happened to be in `(1 of 2)`.

**Right fix:** when multiple member files match a schedule token, iter_schedule_rows should stream all of them (concatenate row iterators). Same pattern as Bug 2 — single-column lookup becomes multi-column / multi-file fan-in.

### Database state after the bad ingest

- `facts.CDR_CET1_CAPITAL`: 32 rows (4 banks × 8 quarters; First-Citizens missing). **Values are Tier 1 capital amounts**, not CET1. For MidFirst/BOK/Frost the numbers happen to be right (no AT1); for Bank OZK they're wrong by ~80 bps.
- `facts.CDR_HTM_FAIRVAL`: 8 rows (First-Citizens × 8 quarters only). Missing 4 banks because of Bug 3.
- `ratios.cet1`: `data_quality='ok'` with wrong values for 4 banks, `partial` for First-Citizens.
- `ratios.htm_loss_t1`: `data_quality='ok'` for First-Citizens only, `partial` for the others.

**No rollback needed** — the fix re-ingests and overwrites via the existing idempotent upsert path. The restatement detector will fire on Bank OZK's CET1 (82 bp diff = real change), drop a `quality_log` row, and recompute. Audit-trail clean.

## Recommended next step (1-5 sentences)

**Run `/ultraplan` in a fresh session to fix the CDR ingest** — scope is isolated to `cdr_schema.py` + `cdr.py` + ~2-3 tests, the bug is fully characterized above, and a sandbox iteration on a focused fix is exactly the right tool. **In parallel, merge PR #1 to `main` and update HANDOFF accordingly** — the dashboard is independent of CDR data quality; once the CDR fix re-ingests, `cet1` and `htm_loss_t1` flip to correct `ok` values with zero dashboard code change. Do not start Sprint 2 (per-ratio drilldown) until both have landed — the drilldown needs to show restatement provenance for cells that change between this session's bad data and the post-fix correct data, and that flow is easier to design once both PRs are merged.

## Sprint 1 PR #1 — what's left

Steps the human owns (I cannot squash-merge to main without explicit per-action approval — the user wants a heads-up on irreversible actions):

1. **Self-review the diff** at https://github.com/ConnorTipton/Peerbench/pull/1/files
2. **Squash-merge** when satisfied:
   ```bash
   gh pr merge 1 --squash --delete-branch
   ```
3. **After merge, ask Claude to update HANDOFF.md** to reflect Sprint 1 having shipped (delete the "Sprint 1 lives in PR #1" sections, replace with a "Sprint 1 merged at <sha>" summary). Trivial 5-min cleanup.

## Definition of Done — Phase 1, where we actually stand

The Phase-1 DoD bar from `CLAUDE.md` is: "ratios match FDIC pre-computed ±2 bps on 5-bank sample; restatement detector wired and logging."

- **13 of 15 mapped ratios pass the bar.** `acl_loans`, `acl_npl`, `eff_ratio`, `loans_deposits`, `nco_ratio`, `nim`, `npl_ratio`, `roa`, `roe`, `tier1_lev`, `tier1_rbc`, `total_rbc`, `yield_ea` — all within fractions of a bp. Two unmapped ratios `cet1` (FDIC code `IDT1CER`) and `htm_loss_t1` (no FDIC pre-computed) are blocked on the CDR fix.
- **Once the CDR fix lands**, `cet1` joins the mapped set with target <2 bps drift; `htm_loss_t1` enters at `ok` for all 5 banks (currently 1/5).
- **`top_loan_cat` (RC-C expansion)** remains the one Phase-1 `NotImplementedError`. Deferrable to Phase 2 if the dashboard doesn't surface it in v1 (it doesn't currently).
- **Restatement detector is wired and end-to-end smoke-tested** (Day 4). One real `quality_log` row exists for MidFirst-Q4-NIM (synthetic diff during smoke).

## Files of interest for the CDR fix

The next agent should start by reading these in order:

1. `/Users/connortipton/Projects/Peerbench/HANDOFF.md` — this file (especially "Open issues" + "Recommended next step")
2. `/Users/connortipton/Projects/Peerbench/src/peerbench/ingest/cdr_schema.py` — single-column pinning; needs to become multi-column lookup
3. `/Users/connortipton/Projects/Peerbench/src/peerbench/ingest/cdr.py` — `iter_schedule_rows`, `_find_member`; needs multi-file fan-in (Bug 3) and multi-column row-lookup (Bug 2)
4. `/Users/connortipton/Projects/Peerbench/tests/unit/test_cdr_parser.py` and `test_cdr_schema.py` — existing tests; will need new cases for multi-column fallback + multi-file streaming
5. `/Users/connortipton/Projects/Peerbench/docs/cdr-ingest.md` — manual download procedure; no edits needed
6. `/Users/connortipton/Projects/Peerbench/docs/divergences.md` — update post-fix to remove the "awaiting first live CDR ZIP" status on `cet1` and `htm_loss_t1`

## How to run things (smoke commands)

`.env.local` at repo root is populated. Inside the project dir:

```bash
uv run pytest                                       # 63 tests — should still pass post-fix
uv run peerbench info                               # sanity: 30 handlers, 65 field codes
uv run peerbench ingest-cdr --certs 4063,4214,110,11063,5510 --quarters 8
for c in 4063 4214 110 11063 5510; do uv run peerbench compute --cert "$c" --quarters 8; done
uv run peerbench validate --certs 4063,4214,110,11063,5510 --quarters 8 \
  --write-snapshot docs/validation-snapshot.md
```

**Acceptance criterion for the CDR fix:** `validate` gate reports `PASS` with mean <2 bps / max <5 bps across **15 mapped ratios** (currently 13 — `cet1` + `htm_loss_t1` join once `IDT1CER` and an HTM cross-check are computable for all 5 banks).

**Web dashboard:**
```bash
cd web && npm install && npm run dev
```
With `web/.env.local` populated from the user's Supabase project URL + anon key (URL: `https://mmefodhnpybyxzpaobmt.supabase.co`).

## Architecture conventions to honor

(Repeating from `CLAUDE.md` so this survives into a fresh context.)

- **Decimal end-to-end.** No `float(` casts in the value path. Contract test enforces.
- **Ratio handler registry.** Every ratio has a row in `ratio_defs` AND a registered handler in `peerbench.ratio_engine.handlers`. Contract test enforces 1:1 + AST-hash drift detection.
- **Suppression is pipeline-level** via `ratio_defs.suppress_when JSONB`. Handlers stay pure.
- **All handler versions stay at `"v1"`.** Phase 1 hasn't shipped externally. To change a handler body during Phase 1: edit, delete `tests/contract/handler_ast_snapshot.json`, run pytest once to regenerate, then run again to confirm clean.
- **No formula logic in TS or Excel.** Dashboard reads `ratios.value` only.
- **Post-CECL nomenclature.** ACL, never ALLL.

## What NOT to redo

- **Don't re-stage CDR ZIPs** — they're in `cache/cdr/2024-Q1.zip` … `cache/cdr/2025-Q4.zip` (8 files for the gate + `2026-Q1.zip` extra).
- **Don't re-apply institution names** — already done; `sql/seed_institution_names.sql` is on the branch for the post-merge `main`.
- **Don't bump handler `version="v1"` during Phase 1.**
- **Don't trust the BOK cert 4862 or Cullen/Frost cert 5560** from the original plan — they're inactive. Use **4214** and **5510**.

## Today's date

2026-05-20. Most recent finalized quarter (90-day publication latency) is **2025-Q4** (`report_date = 2025-12-31`).

## User context / preferences (from memory)

- Connor, prepping for Summer 2026 FP&A internship at MidFirst Bank.
- Solo developer, fresh repo, this project doubles as portfolio material.
- High autonomy ("just go with your best recommendations") but wants a heads-up before live DB changes, pushes, or other irreversible actions.
- Prefers check-ins at chunk boundaries, not narration of every step.
- Uses `/ultraplan` for well-scoped sandboxed implementation; PR-back pattern is established.
