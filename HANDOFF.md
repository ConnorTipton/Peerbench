# Peerbench — handoff (2026-05-20 night, Phase 1 + Phase 2 Sprint 1 closed)

You are continuing work on Peerbench, Connor's FP&A internship-prep project at `/Users/connortipton/Projects/Peerbench`. Read `CLAUDE.md` and `PLAN.md` (v1.3) before doing anything substantive.

## TL;DR

- **Phase 1 is fully closed.** Validation gate `PASS` with N=540, mean=0.02 bps, max=0.51 bps. `cet1` joined the per-ratio table at 0.00/0.00 bps vs FDIC `IDT1CER`. `htm_loss_t1` is `ok` across the full 5-bank × 8-quarter grid. **`top_loan_cat` (RC-C expansion) is the only remaining `NotImplementedError`** — formally deferable to Phase 4 per `docs/divergences.md`.
- **PR #2 (CDR ingest data-quality fix) merged at `3067950`.** Closed three bugs: wrong CET1 MDRM (`RCOA8274` → `(RCOAP859, RCFAP859)`), missing multi-column candidate lookup, and missing multi-file fan-in for column-split RC-B.
- **PR #1 (Phase 2 Sprint 1 dashboard + polish) squash-merged at `e000cc1`.** Closes Sprint 1: Next.js 16 + Tailwind v4 scaffold, 30-ratio × 5-peer matrix for the latest quarter, anchor selector, sticky header/column, design tokens from `docs/design.md` in `@theme`. Polish landed before merge — per-cell restatement scoping via handler-AST-derived deps and a <1s load benchmark (see "Sprint 1 polish" below).
- **Test count: 78 passing** (was 74 post-PR-#2; +4 tests for the field-deps contract + ingest scope + CBLR suppression-dep regression).
- **Working tree:** on `main` @ `e000cc1`, clean (`.gitignore` carries an external `.gstack/` addition from gstack tooling, not from any of my work).
- **DB state unchanged:** 5 banks × 8 quarters; 29 of 30 ratios `ok`; `top_loan_cat` lone `partial`.

## What landed this session (Sprint 1 polish → PR #1 squash merge `e000cc1`)

Branch `phase-2-sprint-1-dashboard-scaffold`. Three additional commits on top
of the prior 4 web commits before squash:

1. **`9a6dbd4` — `feat(ratio-engine):` handler field-dep extraction + snapshot CLI.**
   New `src/peerbench/ratio_engine/field_deps.py` walks each handler's AST,
   unions `RATIO_DEPENDENCIES` transitive closure, and merges
   `SUPPRESS_KEY_FIELDS` (new in `suppression.py`: maps `suppress_when` keys
   to FFIEC field codes). `peerbench export-field-deps` writes the snapshot
   to `web/lib/ratio-field-deps.generated.json`. A new contract test
   (`TestFieldDepsSnapshot`) enforces snapshot ↔ AST in lock-step.
2. **`73177c6` — `fix(ingest):` scope restatement partial flip to consumer
   ratios.** `ingest/quality_log.py` now flips
   `Ratio.ratio_id IN (consumers_of_restated_field)` instead of every ratio
   for the bank-quarter. Skips the UPDATE when the field has no registered
   consumer.
3. **`5370804` — `feat(web):` per-cell restatement marker keyed by
   `ratio_id`.** `queries.ts` selects `field_code` from `quality_log`,
   resolves to ratio_ids via the snapshot, builds
   `Set<${cert}|${ratio_id}>`. Dashboard never sees raw field codes.

### Sprint 1 polish — gap closure summary

- **Gap (a) — per-cell restatement scoping.** Before: any restatement for
  `(cert, quarter_id)` lit up every cell in that bank's column (60 cells of
  180 with the current seed). After: 5 marked cells matching `docs/design.md`
  exactly (4 NIM-consuming ratios on MidFirst + 1 CET1 on Bank OZK).
  Verified end-to-end in browser.
- **Gap (b) — <1s load benchmark.** Dev-mode timings on localhost:3000 with
  Supabase round-trip: TTFB 566 ms, DOM Ready 614 ms, **Load 812 ms**, 80 KB
  payload. Under the <1s spec even with Turbopack compile overhead; prod
  build will be lower.
- **Codex review:** 1 P1 (CBLRIND missing from suppression deps —
  `tier1_rbc`/`total_rbc`/`cet1` would have skipped the partial flip on
  CBLR-election changes) **fixed in `9a6dbd4`** via `SUPPRESS_KEY_FIELDS`.
  2 P2s justified in PR body: (i) Python re-runs AST at runtime while web
  reads the snapshot — contract test is the cross-layer guarantee; (ii)
  `f.avg(...)` represents a field dep but not a temporal one (cross-quarter
  recompute deferred to Sprint 2).

## Previously landed (PR #2, squash merge `3067950`)

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

### Phase 2 — Sprint 1 closed (PR #1 merged at `e000cc1`)
- Dashboard renders the 30-ratio × 5-peer matrix for the latest renderable quarter (2025-Q4). Real institution names, anchor tint on MidFirst column, sticky header + first column, design tokens from `docs/design.md` encoded in Tailwind v4 `@theme`.
- Restatement marker is per-cell (per `docs/design.md` spec), keyed by `(cert, ratio_id)`. The field→ratio mapping comes from `web/lib/ratio-field-deps.generated.json`, derived from handler ASTs by `peerbench export-field-deps`. Contract test `TestFieldDepsSnapshot` keeps it in lock-step with handler bodies.
- Load time: 812 ms in dev mode on localhost (TTFB 566 ms, DOM Ready 614 ms, 80 KB payload). Production will be lower.

### Phase 2 — Sprint 2 onward (next up)
- Per-peer sort, ratio category collapse/expand, drill-down detail view per `PLAN.md` v1.3.
- Restatement tooltip: `queries.ts` already pulls `old_value`/`new_value`/`detected_at` from `quality_log`; UI work remains.
- Cross-quarter recompute for `f.avg(...)` consumers (codex P2 from PR #1 — a restatement to a prior quarter's `DEPI` should mark the current quarter's `cost_funds`/`nis` too).
- Dashboard polish per `docs/design.md` — conditional formatting heat map (top/bottom quartile tints), regulatory threshold amber flags.

### Phase 3 — Hosting & cron (not started)
- Daily ingest cron via GitHub Actions. Weekly Supabase backup. Vercel Hobby deploy of `web/`.
- Supabase RLS still disabled; pre-prod work to enable RLS + add a permissive read policy (public FFIEC data, low blast radius).

### Phase 4 — Polish (not started)
- Insights generation, Excel export from `ratios` table, README + Loom.

## What's NOT changed by PR #1 polish

- Handler bodies (`compute_*`) — untouched; AST snapshot clean. All handlers stay at `version="v1"` per the Phase 1 contract.
- `data/ratios.csv` — untouched.
- `tests/contract/handler_ast_snapshot.json` — untouched.
- Validation gate — untouched. `peerbench validate` still PASS at mean 0.02 bps / max 0.51 bps; PR #1 added no ratio definitions or formula changes.

## Quick verify (run when picking up the session)

```bash
git -C /Users/connortipton/Projects/Peerbench log main -2 --oneline
# Expect:
#   e000cc1 Phase 2 Sprint 1 — Next.js 16 scaffold + ratio matrix (#1)
#   3067950 fix(ingest): CDR multi-column lookup + multi-file fan-in ... (#2)

cd /Users/connortipton/Projects/Peerbench && uv run pytest 2>&1 | tail -3
# Expect: 78 passed

uv run peerbench export-field-deps --out /tmp/check.json
diff /tmp/check.json web/lib/ratio-field-deps.generated.json
# Expect: identical (no diff). Drift means a handler edit landed without
# regenerating the snapshot — re-run `peerbench export-field-deps` and
# commit the JSON.

cd web && npm install && npm run dev
# Open http://localhost:3000 — confirm:
#   • MidFirst column: `r` superscript on NIM, Efficiency Ratio, PPNR,
#     Non-int Inc/Rev (4 NIM consumers)
#   • Bank OZK column: `r` on CET1 only
#   • Other peer columns: no `r` markers
```

If any diverge, surface to the user before doing substantive work.

## How to run things (smoke commands)

`.env.local` and `web/.env.local` are populated.

```bash
# Python pipeline
uv run pytest                                       # 78 tests
uv run peerbench info                               # 30 handlers, 65 field codes
uv run peerbench ingest --cert 4063 --quarters 1    # FDIC API
uv run peerbench ingest-cdr --certs 4063,4214,110,11063,5510 --quarters 8  # CDR ZIPs
uv run peerbench compute --cert 4063 --quarters 1   # compute ratios
uv run peerbench validate --certs 4063 --quarters 1 # bp diff vs FDIC precomputed
uv run peerbench export-field-deps                  # regenerate handler→field snapshot

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
- **Handler field-dependency snapshot.** `peerbench export-field-deps` walks each handler's AST and writes `web/lib/ratio-field-deps.generated.json`. The ingest restatement callback and the dashboard's per-cell marker both consume it. After any handler edit that touches field references, regenerate and commit; the contract test will fail otherwise. New `suppress_when` keys also require an entry in `SUPPRESS_KEY_FIELDS` in `ratio_engine/suppression.py`.
- **No formula logic in TS or Excel.** Dashboard and (future) Excel export read `ratios.value` only.
- **Post-CECL nomenclature.** ACL, never ALLL.

## What NOT to redo

- **Don't re-stage CDR ZIPs** — `cache/cdr/2024-Q1.zip` … `2025-Q4.zip` are present (+ 2026-Q1.zip extra not yet used).
- **Don't re-apply institution names** — already in DB.
- **Don't re-ingest the 5 banks** unless explicitly asked. Re-ingest is idempotent; not destructive but unnecessary.
- **Don't bump handler `version="v1"`** during Phase 1.
- **Don't trust BOK cert 4862 or Cullen/Frost cert 5560** — inactive. Use **4214** and **5510**.

## Today's date

2026-05-20 (night session). Most recent finalized quarter (90-day publication latency) is **2025-Q4** (`report_date = 2025-12-31`). 2026-Q1 will publish ~late June 2026.

## User context / preferences

- Connor, prepping for Summer 2026 FP&A internship at MidFirst Bank.
- Solo developer, fresh repo, doubles as portfolio material.
- High autonomy ("just go with your best recommendations") but wants a heads-up before live DB changes, force-pushes, or other irreversible actions.
- Prefers check-ins at chunk boundaries; not narration of every step.
- Uses `/codex review` as a routine pre-merge gate; treats codex P2s as worth fixing or explicitly justifying.

## Recommended first action

Pick a direction for the next session. Three reasonable options:

1. **Phase 2 Sprint 2** — per-peer sort, ratio category collapse/expand,
   drill-down detail view, restatement tooltip (data already pulled in
   `queries.ts`), conditional-formatting tints per `docs/design.md`.
2. **Phase 3 hosting** — daily ingest cron via GH Actions, Supabase RLS
   enable + permissive read policy migration, Vercel Hobby deploy of
   `web/`. The cron also doubles as the Supabase 7-day inactivity heartbeat.
3. **Phase 4 Excel export starter** — CLI scaffold for
   `peerbench export --quarter --output` reading from the `ratios` table
   per the design contract (`docs/design.md` §"Excel export design parity").

The continuation prompt at `~/.claude/plans/phase-2-sprint-1-continuation.md`
is now obsolete and can be deleted. The plan file used for this session is
at `~/.claude/plans/next-chat-prompt-humming-taco.md`.
