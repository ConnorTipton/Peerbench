# Peerbench — handoff (2026-05-20 evening, Phase 1 closed; Sprint 1 dashboard PR open)

You are continuing work on Peerbench, Connor's FP&A internship-prep project at `/Users/connortipton/Projects/Peerbench`. Read `CLAUDE.md` and `PLAN.md` (v1.3) before doing anything substantive.

## TL;DR

- **Phase 1 is fully closed.** Validation gate `PASS` with N=540, mean=0.02 bps, max=0.51 bps. `cet1` joined the per-ratio table at 0.00/0.00 bps vs FDIC `IDT1CER`. `htm_loss_t1` is `ok` across the full 5-bank × 8-quarter grid. **`top_loan_cat` (RC-C expansion) is the only remaining `NotImplementedError`** — formally deferable to Phase 4 per `docs/divergences.md`.
- **PR #2 (CDR ingest data-quality fix) was squash-merged to `main` at `3067950`.** Closed three bugs: wrong CET1 MDRM (`RCOA8274` → `(RCOAP859, RCFAP859)`), missing multi-column candidate lookup, and missing multi-file fan-in for column-split RC-B. Now 74 tests passing (was 63).
- **PR #1 (Phase 2 Sprint 1 dashboard scaffold) is rebased on the new `main`, MERGEABLE + CLEAN, awaiting self-review.** https://github.com/ConnorTipton/Peerbench/pull/1. Force-push happened after the rebase; head is at `a052212`.
- **Working tree** as of this handoff: on branch `phase-2-sprint-1-dashboard-scaffold`, clean, in sync with origin. `main` at `3067950`.
- **DB state:** 5 banks × 8 quarters with 29 of 30 ratios `ok`; `top_loan_cat` is the lone `partial`. `CDR_CET1_CAPITAL` + `CDR_HTM_FAIRVAL` facts populated for all (cert, quarter) pairs.

## What landed in this session (PR #2, 8 commits → 1 squash merge `3067950`)

Branch `fix-cdr-multi-column-and-multi-file` cut from `origin/main` at `77076c1`. Eight per-task commits squashed on merge:

1. **`a6e451d` — schema map P859 candidates + plural `cdr_columns` API.** Switched `_STABLE` from `dict[str, str]` to `dict[str, tuple[str, ...]]`. Renamed `cdr_column` → `cdr_columns`.
2. **`74b3585` — parser multi-file fan-in + group header check.** `_find_member` → `_find_members`. `required_columns` shape became `tuple[tuple[str, ...], ...]` (OR-within-group).
3. **`d962fb9` — CLI first-non-empty value extraction.** `ingest-cdr` walks the candidate tuple via `pick_first_non_empty(row, candidates)`.
4. **`81c6ebd` — per-member skip refinement.** Live RC-B 2025-Q4 turned out to be **column-split** (not row-split as the task brief said): part 1 has 242 cols incl. `RCFD1773`, part 2 has 62 disjoint `RCONG*` memo cols. Parser now skips members lacking the required group rather than failing per-file; raises only if NO matching member satisfies the groups.
5. **`3bfe2a0` — post-fix snapshot.** Regenerated `docs/validation-snapshot.md`.
6. **`80de7de` — `RCON1773` HTM fallback.** Live ingest revealed 4 of 5 banks populate `RCON1773` (domestic-only), only First-Citizens populates `RCFD1773`. Added the second candidate; same multi-column pattern as CET1.
7. **`056332d` — divergences + cdr-ingest docs.** Moved `cet1` and `htm_loss_t1` to "fully resolved" in `docs/divergences.md`. Updated MDRM citations in `docs/cdr-ingest.md`.
8. **`af75f93` — codex P2 cleanups.** Moved `_coerce_cdr_value` → `coerce_cdr_value` in `cdr.py`; added `src/peerbench/ingest/cdr.py` to `VALUE_PATH_MODULES`; `pick_first_non_empty` now warns on divergent populated candidates; `ingest-cdr` tracks `matched_certs` set per `(qid, label)` and prints `N/M certs matched` + a stderr WARN line on gaps; added a 3-file fan-in regression test + `coerce_cdr_value` roundtrip test; fixed inverted RCOA/RCFA prefix semantics in `docs/divergences.md`.

**Codex review GATE: PASS** (no P1s). All 5 P2s addressed in `af75f93`.

**Empirical pins (verified against `cache/cdr/2025-Q4.zip` on 2026-05-20):**

- `CET1_CAPITAL → ("RCOAP859", "RCFAP859")` — Bank OZK `RCOAP859/RWAJT = 11.7244%` matches FDIC `IDT1CER` exactly.
- `HTM_FAIRVAL → ("RCFD1773", "RCON1773")` — First-Citizens reports both equal at 31790000; the other 4 sample banks populate `RCON1773` only.

## Open items / state of play

### Phase 1 — fully closed
- 29 of 30 ratios at `ok` across the 5×8 grid. `top_loan_cat` is `partial` (raises `NotImplementedError` — intentional defer).
- Restatement detector wired and producing audit-trail rows on each ingest.

### Phase 2 — Sprint 1 in PR #1
- **PR #1 head:** `a052212` on `phase-2-sprint-1-dashboard-scaffold`. Rebased cleanly onto post-PR-#2 main. Confirmed MERGEABLE + CLEAN via `gh pr view 1`.
- **Dashboard renders** the 30-ratio × 5-peer matrix for the latest renderable quarter (2025-Q4). Real institution names, restatement marker visible on the MidFirst Q4 NIM cell, sticky header + first column, anchor highlight on MidFirst column. Design tokens in Tailwind v4 `@theme`.
- **Reviewer-flagged soft items already fixed on the branch:** arbitrary-value escapes → utility classes; positional anchor detection → typed `ColumnMeta.cert` via TanStack module augmentation.
- **Two outstanding Sprint-1 polish gaps** worth confirming before merge:
  - Restatement indicator is per-cell currently — confirm against `docs/design.md` whether row-/column-level rollup is also expected.
  - <1s load target wasn't formally benchmarked; time it with browser dev tools before declaring Sprint 1 done.

### Phase 2 — Sprint 2 onward (not yet started)
- Per-peer sort, ratio category grouping, drill-down detail view per `PLAN.md` v1.3.
- Dashboard polish per `docs/design.md` — banking-grade typography, conditional formatting, tabular-nums.

### Phase 3 — Hosting & cron (not started)
- Daily ingest cron via GitHub Actions. Weekly Supabase backup. Vercel Hobby deploy of `web/`.
- Supabase RLS still disabled; pre-prod work to enable RLS + add a permissive read policy (public FFIEC data, low blast radius).

### Phase 4 — Polish (not started)
- Insights generation, Excel export from `ratios` table, README + Loom.

## What's NOT changed by PR #2

- Handler bodies (`compute_cet1`, `compute_htm_loss_t1`) — untouched; AST snapshot clean.
- `data/ratios.csv` — untouched; `cet1.fdic_precomputed_code = IDT1CER`, `htm_loss_t1.fdic_precomputed_code` still empty (no FDIC pre-computed counterpart).
- `tests/contract/handler_ast_snapshot.json` — untouched; all handlers stay at `version="v1"`.

## Quick verify (run when picking up the session)

```bash
git -C /Users/connortipton/Projects/Peerbench log main -1 --oneline
# Expect: 3067950 fix(ingest): CDR multi-column lookup + multi-file fan-in ... (#2)

git -C /Users/connortipton/Projects/Peerbench log phase-2-sprint-1-dashboard-scaffold --oneline -5
# Expect head a052212 plus 3 rebased web/ commits ahead of main

cd /Users/connortipton/Projects/Peerbench && uv run pytest 2>&1 | tail -3
# Expect: 74 passed

uv run peerbench validate --certs 4063,4214,110,11063,5510 --quarters 8 2>&1 | tail -5
# Expect: Gate: PASS  (N=540, mean=0.02 bps, max=0.51 bps)
```

If any diverge, surface to the user before doing substantive work.

## How to run things (smoke commands)

`.env.local` and `web/.env.local` are populated.

```bash
# Python pipeline
uv run pytest                                       # 74 tests
uv run peerbench info                               # 30 handlers, 65 field codes
uv run peerbench ingest --cert 4063 --quarters 1    # FDIC API
uv run peerbench ingest-cdr --certs 4063,4214,110,11063,5510 --quarters 8  # CDR ZIPs
uv run peerbench compute --cert 4063 --quarters 1   # compute ratios
uv run peerbench validate --certs 4063 --quarters 1 # bp diff vs FDIC precomputed

# Dashboard
cd web && npm install && npm run dev                # http://localhost:3000
```

## Architecture conventions to honor

(Also in `CLAUDE.md`; repeated so they survive into a fresh context.)

- **Decimal end-to-end.** No `float(` casts in the value path. Contract test enforces against `VALUE_PATH_MODULES` which now includes `src/peerbench/ingest/cdr.py`.
- **CDR value coercion** is centralized at `peerbench.ingest.cdr.coerce_cdr_value(raw)`. Callers must NOT add a second str→Decimal coercion point.
- **CDR candidate lookup:** `cdr_columns(quarter_id, label)` returns `tuple[str, ...]`. Callers walk the tuple via `pick_first_non_empty(row, columns)`. Schema map is the source of truth.
- **Parser `required_columns`** semantic is OR-within-group, AND-across-groups, with per-member skip and aggregate fail-loud. Don't bypass.
- **Ratio handler registry.** Every ratio has a row in `ratio_defs` AND a registered handler. Contract test enforces 1:1 + AST-hash drift detection.
- **All handler versions stay at `"v1"`.** Phase 1 hasn't shipped externally. To change a handler body: edit, delete `tests/contract/handler_ast_snapshot.json`, run pytest once to regenerate, then run again clean.
- **No formula logic in TS or Excel.** Dashboard and (future) Excel export read `ratios.value` only.
- **Post-CECL nomenclature.** ACL, never ALLL.

## What NOT to redo

- **Don't re-stage CDR ZIPs** — `cache/cdr/2024-Q1.zip` … `2025-Q4.zip` are present (+ 2026-Q1.zip extra not yet used).
- **Don't re-apply institution names** — already in DB.
- **Don't re-ingest the 5 banks** unless explicitly asked. Re-ingest is idempotent; not destructive but unnecessary.
- **Don't bump handler `version="v1"`** during Phase 1.
- **Don't trust BOK cert 4862 or Cullen/Frost cert 5560** — inactive. Use **4214** and **5510**.

## Today's date

2026-05-20 (evening session). Most recent finalized quarter (90-day publication latency) is **2025-Q4** (`report_date = 2025-12-31`). 2026-Q1 will publish ~late June 2026.

## User context / preferences

- Connor, prepping for Summer 2026 FP&A internship at MidFirst Bank.
- Solo developer, fresh repo, doubles as portfolio material.
- High autonomy ("just go with your best recommendations") but wants a heads-up before live DB changes, force-pushes, or other irreversible actions.
- Prefers check-ins at chunk boundaries; not narration of every step.
- Uses `/codex review` as a routine pre-merge gate; treats codex P2s as worth fixing or explicitly justifying.

## Recommended first action

Open `gh pr view 1 --web` and self-review the Sprint 1 dashboard. Either squash-merge it (if it looks done) or pick up the Sprint 1 polish gaps (restatement rollup, <1s load benchmark). See the next-chat prompt at `~/.claude/plans/phase-2-sprint-1-continuation.md` for the planned next step.
