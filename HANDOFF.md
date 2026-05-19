# Peerbench — handoff from previous session (2026-05-19, end of Day 3)

You are continuing work on Peerbench, Connor's FP&A internship-prep project at `/Users/connortipton/Projects/Peerbench`. Read `CLAUDE.md` and `PLAN.md` (v1.3) for the project plan and conventions before doing anything substantive.

## TL;DR

- Phase 1 Days 1, 2, and 3 are **complete and pushed** to `origin/main` at `48f08a9`.
- 27 of 30 ratios implemented; validated to **mean 0.03 bps, max 0.47 bps** vs FDIC pre-computed across the 5-bank sample for 2025-Q4 (DoD bar: <2 / <5 bps).
- 3 handlers intentionally `raise NotImplementedError`:
  - `cet1` and `htm_loss_t1` need FFIEC CDR ingest (Task 25 plan-mode pause)
  - `top_loan_cat` needs full RC-C subcategory ingest (Day 4+ field expansion)
- Two real validation gaps documented (`npl_ratio` wrong field, `eff_ratio` methodology drift).
- Working tree is clean. Next session starts from a published-and-tested state.

## What landed in Day 3 (commit `48f08a9`)

- **Compute dispatcher** (`src/peerbench/ratio_engine/compute.py`): `load_fact_view` pulls a 5-period FactView, `compute_ratio` runs suppression → handler → classify, `compute_all_for_bank_quarter` walks the topological order. Classifies results as `OkResult` / `PartialResult` / `SuppressedResult` via `data_quality_for()`; catches `MissingFieldError`, `NotImplementedError`, `DivisionByZero`, `InvalidOperation` as `PartialResult`.
- **27 handler bodies** filled across `asset_quality.py`, `balance_sheet.py`, `capital.py`, `concentration.py`, `liquidity.py`, `profitability.py`, `yields.py`.
- **YTD averaging fix** in `nco_ratio` and `cost_funds`: uses `f.quarter_number + 1` observations (FDIC convention — prior Dec + current YTD quarter-ends, giving 2/3/4/5 for Q1/Q2/Q3/Q4). Hardcoded `periods=5` only matched Q4. Caught in codex review, fixed pre-commit.
- **`db/ratio_writer.py`**: `upsert_ratio` with PG `ON CONFLICT (cert, quarter_id, ratio_id) DO UPDATE` — idempotent recompute.
- **CLI**: `peerbench compute --cert N --quarters K` subcommand persists results to the `ratios` table.

## Database state (live Supabase)

- 30 rows in `ratio_defs` (seeded via `peerbench seed-ratios`)
- ~2,320 rows in `facts` (5 banks × 8 quarters × ~58 fields, minus blanks)
- 5 rows in `institutions` (4063, 4214, 110, 11063, 5510)
- 150 rows in `ratios` for `2025-Q4` (**135 `ok`, 15 `partial`** — 27 ok + 3 partial per bank × 5 banks)
- `ratio_defs.suppress_when JSONB` column is live — populated for the 3 CBLR-suppressed ratios (none of the 5-bank sample triggers CBLR; they're all $40B+).

## 5-bank sample — use these certs

| Cert | Bank | Note |
| --- | --- | --- |
| 4063 | MidFirst Bank | Anchor. ~$41B, OK-based, family-owned |
| 4214 | BOK Financial NA | ~$52B. **NOT 4862** — that cert is an inactive defunct bank, original plan was wrong |
| 110 | Bank OZK | ~$40B, CRE-heavy |
| 11063 | First Citizens BancShares | ~$229B, Holding family |
| 5510 | Cullen/Frost (Frost Bank) | ~$53B, TX. **NOT 5560** — also wrong/inactive |

If adding peers, verify `ACTIVE=1` via the FDIC API before locking. Grep `data/fdic_field_reference.csv` for field codes.

## Validation snapshot (2025-Q4, 9 anchor ratios that should match FDIC pre-computed exactly)

```
cert   bank                ratios  mean_bps  max_bps
4063   MidFirst             9       0.019     0.172
4214   BOK Financial        9       0.053     0.473
110    Bank OZK             9       0.013     0.117
11063  First Citizens       9       0.002     0.017
5510   Cullen/Frost         9       0.049     0.443
                          all       0.027     0.473
```

The 9: `nim`, `roa`, `roe`, `yield_ea`, `nco_ratio`, `acl_loans`, `tier1_lev`, `tier1_rbc`, `total_rbc`. Decimal end-to-end discipline + 5-period YTD averaging + correct FDIC field codes is why these match to fractions of a bp.

## Known issues / Day 4 follow-ups

1. **`npl_ratio` is ~1004 bps off vs FDIC's `LNRESNCR`.** Handler in `src/peerbench/ratio_engine/handlers/asset_quality.py` uses `NCLNLS / LNLSGR`. Per `data/fdic_field_reference.csv`, `NCLNLS` is described as "Assets past due 90 days or more, plus assets placed in nonaccrual status" — i.e., noncurrent ASSETS, broader than just loans (despite the misleading `LNLS` in the variable name). Need to find a field for noncurrent LOANS only (try `grep -E '^P9LN|^NCNT' data/fdic_field_reference.csv`).

2. **`eff_ratio` is ~26 bps off vs FDIC's `EEFFR`.** Documented methodology gap: FDIC subtracts amortization of intangibles from `NONIX` in the numerator; we use raw `NONIX`. Two options: add an intangibles-amortization field and subtract, or accept the gap and document. `EEFFR` is industry-standard, so most readers won't notice the small drift.

3. **`cet1` and `htm_loss_t1` deliberately `NotImplementedError`.** Both need FFIEC CDR fields the FDIC API doesn't expose:
   - `cet1` — CET1 capital $ amount from Schedule RC-R Part I (FDIC exposes only the ratio `IDT1CER`)
   - `htm_loss_t1` — HTM fair value from RC-B Memorandum 2 (FDIC exposes amortized cost via `SCHA` but not fair value)
   See the Day 2 plan at `/Users/connortipton/.claude/plans/enter-plan-mode-for-silly-spark.md`, §3 "FFIEC CDR ingest path".

4. **`top_loan_cat` deliberately `NotImplementedError` as of `48f08a9`.** Was previously misclassified as `ok` while only checking 3 of ~10 RC-C subcategories (LNRECONS / LNREMULT / LNRENRES). Codex review caught it. Full implementation needs the rest of RC-C (C&I, consumer, ag, 1-4 family, etc.) — expand `src/peerbench/fdic_fields.py` and re-ingest.

## Open tasks (use `TaskList` to see current state)

- **Task 23 (pending):** Wire real `on_diff` callback for the restatement detector. The seam exists in `src/peerbench/ingest/upsert.py` and accepts an `on_diff` callable; `cli.py:ingest` currently passes nothing. Build a callback that:
  1. Writes a `quality_log` row with `event_type='restated'`, old + new values, in the same session as the upsert (atomic).
  2. Marks affected `ratios` rows as stale — either delete them or set `data_quality='partial'` (decide based on whether `compute` will re-run automatically).
  3. Wire it into `cli.py`'s `ingest` command via the existing seam.
  Test by re-ingesting a quarter that was already ingested — should produce 0 quality_log rows since values are unchanged. Then manually mutate a fact and re-ingest — should produce 1 quality_log row.

- **Task 25 (pending):** Plan-mode for FFIEC CDR ingest. The plan-approved scope is in the existing Day 2 plan file. Build the CDR ZIP downloader, per-quarter schema map for RC-R Part I (CET1 capital $) and RC-B Memorandum 2 (HTM fair value), streaming TSV parser (the CDR uses Subject Data Format = TSV inside ZIP, **not openpyxl** despite the original PLAN.md typo we fixed). Then implement the `cet1` and `htm_loss_t1` handler bodies. Bump `formula_version` for both, regenerate the AST snapshot, and re-validate.

- **Day 4 (per PLAN.md):** Validation pass — fix `npl_ratio` field, document `eff_ratio` methodology drift, write `docs/ratios/nim.md` worked example, document all divergences.

- **Top_loan_cat (deferred from Day 3):** Expand `src/peerbench/fdic_fields.py` with the rest of RC-C, re-ingest the 5 banks, then re-implement the handler body. Or defer to Phase 2 if the dashboard doesn't need it.

## How to run things (smoke commands)

`.env.local` is fully populated. Inside the project dir:

```bash
uv run pytest                                       # 21 tests (decimal, http resilience, contract)
uv run peerbench info                               # sanity: 30 handlers, 61 fields
uv run peerbench seed-ratios                        # idempotent re-seed of ratio_defs
uv run peerbench ingest --cert 4063 --quarters 1    # one bank, one quarter
uv run peerbench compute --cert 4063 --quarters 1   # compute ratios, persist
uv run ruff check src tests
uv run ruff format --check src tests
```

DB queries via `pg8000` inline (psql isn't installed):

```bash
set -a && source .env.local && set +a
uv run --with pg8000 python <<'PY'
import os, pg8000.dbapi, urllib.parse as up
url = up.urlparse(os.environ["DATABASE_URL"])
conn = pg8000.dbapi.connect(
    user=up.unquote(url.username), password=up.unquote(url.password),
    host=url.hostname, port=url.port or 5432,
    database=url.path.lstrip("/"), ssl_context=True,
)
# ...
PY
```

## Architecture conventions to honor

(Also in `CLAUDE.md`; repeat here so they survive into a fresh context.)

- **Decimal end-to-end.** NO `float(` casts in the value path. The contract test at `tests/contract/test_ratio_registry.py` enforces this with a grep. Adding `float(` will break CI.
- **Ratio handler registry.** Every ratio has a row in `ratio_defs` (human-readable formula = source of truth for documentation) AND a registered handler in `peerbench.ratio_engine.handlers` (Python = source of truth for execution). A contract test enforces 1:1 correspondence + AST-hash drift detection.
- **YTD averaging.** Use `f.avg(field, periods=f.quarter_number + 1)` — FDIC's YTD average convention is prior Dec + current YTD quarter-ends (2/3/4/5 observations for Q1/Q2/Q3/Q4). Hardcoding `periods=5` would only be correct at Q4. Where FDIC exposes pre-averaged fields (`ASSET5`, `EQ5`, `ERNAST5`), prefer those — they're already averaged correctly per quarter.
- **Suppression is pipeline-level.** CBLR suppression lives in `ratio_defs.suppress_when JSONB` column; the dispatcher calls `should_suppress()` before invoking a handler. Handlers stay pure.
- **Annualization** via `FactView.annualize_factor()` returning Q1=4, Q2=2, Q3=4/3, Q4=1.
- **All handler versions stay at `"v1"`.** The contract test `TestHandlerVersions.test_all_handlers_at_v1` enforces this — Phase 1 hasn't shipped externally yet, so semantic versioning starts when Phase 2 publishes the dashboard. To change a handler body during Phase 1: edit, delete `tests/contract/handler_ast_snapshot.json`, run pytest once to regenerate, then run again to confirm clean. Don't bump to `"v2"` yet.
- **Today's date is 2026-05-19.** Most recent finalized quarter is 2025-Q4. The CLI uses `PUBLICATION_LATENCY_DAYS=90` (in `src/peerbench/quarters.py`), not the 35-day filing deadline — FDIC publishes ~60-90 days after quarter end.
- **No formula logic in TS or Excel.** The dashboard (Phase 2) and Excel export (Phase 4) read the `ratios` table only.
- **Post-CECL nomenclature.** ACL, never ALLL.

## What NOT to redo

- Don't re-ingest the 5 banks unless explicitly asked — they're already in Supabase.
- Don't re-apply the `suppress_when JSONB` migration — it's live.
- Don't recreate Day 1/2/3 artifacts (already committed and pushed at `48f08a9`).
- Don't use `--base` or `--uncommitted` with a PROMPT to `codex review` in CLI v0.131.0 — they're mutually exclusive. Stage first (`git add -A`) and call `codex review "$PROMPT"` with no diff flag.
- Don't trust the BOK cert (4862) or Cullen/Frost cert (5560) from the original plan — they're inactive. Use **4214** and **5510**.
- Don't bump handler `version="v1"` during Phase 1 — the contract test forbids it. See the version note above.

## Recommended first action

Read these three files in order before touching anything:
1. `/Users/connortipton/Projects/Peerbench/PLAN.md` — project plan v1.3
2. `/Users/connortipton/Projects/Peerbench/CLAUDE.md` — conventions
3. `/Users/connortipton/.claude/plans/enter-plan-mode-for-silly-spark.md` — Day 2 architecture plan (the load-bearing decisions)

Then check git state:

```bash
git -C /Users/connortipton/Projects/Peerbench log --oneline -3
git -C /Users/connortipton/Projects/Peerbench status --short
```

Working tree should be clean and at `48f08a9` (or beyond if Connor pushed more after writing this).

Then ask the user what they want to do. Most likely menu:
- **(a)** Task 23: real `on_diff` callback for the restatement detector. Medium chunk, infrastructure for Day 4 validation.
- **(b)** Task 25: open plan-mode for FFIEC CDR ingest. Biggest remaining Phase 1 piece — unlocks `cet1` and `htm_loss_t1`.
- **(c)** Day 4 validation cleanup: fix `npl_ratio` field, document `eff_ratio` gap, write `docs/ratios/nim.md` worked example.

## User context / preferences (from memory)

- Connor, prepping for Summer 2026 FP&A internship at MidFirst Bank.
- Solo developer, fresh repo, this project doubles as portfolio material.
- High autonomy ("just go with your best recommendations") but wants a heads-up before live DB changes, pushes, or other irreversible actions.
- Prefers check-ins at chunk boundaries, not narration of every step.
- Reachable feedback signals: when shown a plan, picks an option or asks targeted clarifying questions rather than asking for more options.
