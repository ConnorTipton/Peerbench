# Peerbench — handoff from previous session (2026-05-19, Task 25 infra landed)

You are continuing work on Peerbench, Connor's FP&A internship-prep project at `/Users/connortipton/Projects/Peerbench`. Read `CLAUDE.md` and `PLAN.md` (v1.3) for the project plan and conventions before doing anything substantive.

## TL;DR

- **Phase 1 ratio coverage at 29/30**, up from 27/30. `cet1` and `htm_loss_t1` handler bodies shipped this session (Task 25); only `top_loan_cat` remains `NotImplementedError`. See `docs/divergences.md`.
- **FFIEC CDR ingest infrastructure complete.** `peerbench ingest-cdr` reads cached Subject Data Format ZIPs from `cache/cdr/YYYY-Qn.zip`, streams the inner TSVs (RC-R Part I + RC-B Memo 2), maps RSSD→Cert, and upserts CDR-namespaced field codes (`CDR_CET1_CAPITAL`, `CDR_HTM_FAIRVAL`) through the existing on-diff/restatement-detector pipeline.
- **One manual step remains before validation closes.** FFIEC's bulk endpoint is a form-driven .aspx app that can't be auto-downloaded. The user must stage 8 ZIPs in `cache/cdr/` per [`docs/cdr-ingest.md`](./docs/cdr-ingest.md) before the live-ingest + recompute + validate gate can run. The CLI fails cleanly with full instructions if a ZIP is missing.
- **Restatement detector is wired and smoke-tested end-to-end.** Synthetic diff → quality_log row + 30 ratios flipped to partial → next compute restores to ok.
- **57 tests passing** (was 43 at HEAD `c5d9ba0`; +14 new CDR parser + schema-map tests this session). All Day 4 commits pushed to `origin/main`; the Task 25 work is uncommitted locally.
- **Remaining Phase 1 work:** stage CDR ZIPs and run the validation gate. Then `top_loan_cat` (RC-C expansion) — optional, can slide to Phase 2 if the dashboard doesn't surface it in v1.

## What landed in Day 4 (8 commits, `943b23f`…`bd52169`)

In dependency order:

1. **`data(fields): add EAMINTAN + NCLNLSR; fix npl_ratio/acl_npl FDIC mapping`** (`943b23f`) — CSV mapping bug: `npl_ratio` was being compared to `LNRESNCR` (allowance/noncurrent) instead of `NCLNLSR` (noncurrent/loans). Handler was right all along. Filled `acl_npl.fdic_precomputed_code = LNRESNCR` too. Added `EAMINTAN` + `NCLNLSR` to `fdic_fields.py`.
2. **`fix(ratios): eff_ratio subtracts EAMINTAN to match FDIC EEFFR`** (`7da8ff6`) — Handler now subtracts amortization of intangibles from NONIX. Closes the 26 bps drift. AST snapshot regenerated.
3. **`feat(validate): peerbench validate CLI + snapshot writer`** (`7c115a2`) — New subcommand; pulls ok ratios + matching FDIC pre-computed, computes per-row bp diffs, writes `docs/validation-snapshot.md`. Reusable for the Phase 3 daily-cron deploy guard. Decimal-clean (added to VALUE_PATH_MODULES). 9 unit tests.
4. **`feat(ingest): wire on_diff callback to log restatements + mark ratios stale`** (`5ab585f`) — New module `src/peerbench/ingest/quality_log.py`; `make_quality_log_callback(session)` returns the `OnDiffCallback`. Wired into `cli.py:ingest`. 5 unit tests.
5. **`fix(ratios): loans_deposits uses LNLSNET to match FDIC LNLSDEPR`** (`4180ac1`) — Surprise outlier surfaced by the new validate harness: gross-vs-net loans was producing ~100 bps drift. One-line handler swap. AST snapshot regenerated.
6. **`docs(validation): post-Day-4 snapshot — PASS (5 banks × 8 quarters)`** (`f00d246`) — First validation snapshot.
7. **`docs(day-4): NIM worked example + divergences catalog + HANDOFF refresh`** (`551b991`) — `docs/ratios/nim.md` (template for the other 29), `docs/divergences.md` (permanent home for the divergence catalog), and the prior HANDOFF rewrite.
8. **`docs: fix aggregate mean bps (0.04 -> 0.02) in HANDOFF + divergences`** (`bd52169`) — Stat typo fix to match the actual snapshot.

**Day 4 lesson learned:** the `loans_deposits` ~100 bps gap (commit 5) was invisible until the validate harness landed in commit 3. Days 1–3 had measured only 9 anchor ratios by manual SQL; the new harness covers all 13 ratios with mapped FDIC codes and is the reason we caught + fixed the gross/net loans discrepancy. Treat `peerbench validate` as the first thing to run when picking up a stale session — it's the fastest "is anything broken?" signal.

## Database state (live Supabase)

- 30 rows in `ratio_defs` (re-seeded; Day 4 changes to 5 rows of CSV metadata applied)
- ~2,400 rows in `facts` (5 banks × 8 quarters × 60 fields with values; 60 = 58 + EAMINTAN + NCLNLSR)
- 5 rows in `institutions` (4063, 4214, 110, 11063, 5510)
- ~1,200 rows in `ratios` (5 banks × 8 quarters × 30 ratios). Per (cert, quarter): 27 ok + 3 partial in recent quarters, 24 ok + 6 partial in older quarters where some fields are missing.
- 1 row in `quality_log` — from the Day 4 on_diff smoke test (cert 4063, 2025-Q4, NIM, `event_type='restated'`, old=1097000, new=1097635). Real evidence the detector works end-to-end. Safe to leave (it's an audit-trail artifact) or `DELETE FROM quality_log WHERE id=1;` if you want a clean baseline before the next live ingest.

## 5-bank sample — use these certs

| Cert | Bank | Note |
| --- | --- | --- |
| 4063 | MidFirst Bank | Anchor. ~$41B, OK-based, family-owned |
| 4214 | BOK Financial NA | ~$52B. **NOT 4862** — that cert is an inactive defunct bank |
| 110 | Bank OZK | ~$40B, CRE-heavy |
| 11063 | First Citizens BancShares | ~$229B, Holding family |
| 5510 | Cullen/Frost (Frost Bank) | ~$53B, TX. **NOT 5560** — also inactive |

If adding peers, verify `ACTIVE=1` via the FDIC API before locking. Grep `data/fdic_field_reference.csv` for field codes.

## Validation status

See `docs/validation-snapshot.md` for the latest snapshot. Re-run any time:

```bash
uv run peerbench validate --certs 4063,4214,110,11063,5510 --quarters 8 \
  --write-snapshot docs/validation-snapshot.md
```

## Known issues / open items

See `docs/divergences.md` — single source of truth for `NotImplementedError` handlers, methodology divergences, resolved-in-Day-4 + Task-25 items, and within-bar residuals.

## Open tasks

- **Task 25 finish-line (manual + verification):** stage the 8 FFIEC CDR Subject Data Format ZIPs per [`docs/cdr-ingest.md`](./docs/cdr-ingest.md), then run:
  ```bash
  uv run peerbench ingest-cdr --certs 4063,4214,110,11063,5510 --quarters 8
  for c in 4063 4214 110 11063 5510; do uv run peerbench compute --cert "$c" --quarters 8; done
  uv run peerbench validate --certs 4063,4214,110,11063,5510 --quarters 8 --write-snapshot docs/validation-snapshot.md
  ```
  Expect the snapshot to grow from 13 mapped ratios to 15 (cet1, htm_loss_t1 join) and stay PASS. **First live ingest verifies the MDRM codes** (`RCOA8274`, `RCFD1773`) pinned in `src/peerbench/ingest/cdr_schema.py` — if `cet1` differs from `IDT1CER` by more than a couple bps, the domain prefix (`RCOA` vs `RCFD` vs `RCON`) likely needs adjustment.
- **`top_loan_cat` (deferred):** expand `src/peerbench/fdic_fields.py` with the rest of RC-C, re-ingest 5 banks, implement handler. Or defer to Phase 2 if the dashboard doesn't surface it in v1.
- **Phase 2 kickoff:** Next.js 16 dashboard. Once cet1/htm ZIPs are staged and ratios recomputed, all 29 Phase-1-mandate ratios will be in the `ratios` table with the right values + restatement flagging; the frontend just needs to render them. See PLAN.md Phase 2 for the design contract and `docs/design.md` for the token spec.

## How to run things (smoke commands)

`.env.local` is fully populated. Inside the project dir:

```bash
uv run pytest                                       # 57 tests
uv run peerbench info                               # sanity: 30 handlers, 65 field codes (63 FDIC + 2 CDR)
uv run peerbench seed-ratios                        # idempotent re-seed of ratio_defs
uv run peerbench ingest --cert 4063 --quarters 1    # FDIC API: one bank, one quarter
uv run peerbench ingest-cdr --certs 4063 --quarters 1  # CDR ZIPs (cache/cdr/<qid>.zip must be staged)
uv run peerbench compute --cert 4063 --quarters 1   # compute ratios, persist
uv run peerbench validate --certs 4063 --quarters 1 # bp diff vs FDIC precomputed
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

- **Decimal end-to-end.** NO `float(` casts in the value path. The contract test at `tests/contract/test_ratio_registry.py` enforces this with a grep across `decimal_.py`, `ingest/fdic.py`, `ingest/upsert.py`, `ratio_engine/*`, and `validate.py`. Adding `float(` will break CI.
- **Ratio handler registry.** Every ratio has a row in `ratio_defs` (human-readable formula = source of truth for documentation) AND a registered handler in `peerbench.ratio_engine.handlers` (Python = source of truth for execution). A contract test enforces 1:1 correspondence + AST-hash drift detection.
- **YTD averaging.** Use `f.avg(field, periods=f.quarter_number + 1)` — FDIC's YTD average convention is prior Dec + current YTD quarter-ends (2/3/4/5 observations for Q1/Q2/Q3/Q4). Hardcoding `periods=5` would only be correct at Q4. Where FDIC exposes pre-averaged fields (`ASSET5`, `EQ5`, `ERNAST5`), prefer those.
- **Suppression is pipeline-level.** CBLR suppression lives in `ratio_defs.suppress_when JSONB` column; the dispatcher calls `should_suppress()` before invoking a handler. Handlers stay pure.
- **Annualization** via `FactView.annualize_factor()` returning Q1=4, Q2=2, Q3=4/3, Q4=1.
- **Restatement detector** is wired (Day 4). `cli.py:ingest` passes `make_quality_log_callback(session)` to `upsert_fact`; on diff, the callback inserts a `quality_log` row and UPDATEs `ratios.data_quality='partial'` for the affected `(cert, quarter_id)`. Next `compute` run promotes back to `ok`.
- **All handler versions stay at `"v1"`.** The contract test `TestHandlerVersions.test_all_handlers_at_v1` enforces this — Phase 1 hasn't shipped externally yet. To change a handler body during Phase 1: edit, delete `tests/contract/handler_ast_snapshot.json`, run pytest once to regenerate, then run again to confirm clean. Don't bump to `"v2"` yet.
- **Today's date is 2026-05-19.** Most recent finalized quarter is 2025-Q4. The CLI uses `PUBLICATION_LATENCY_DAYS=90` (in `src/peerbench/quarters.py`), not the 35-day filing deadline — FDIC publishes ~60-90 days after quarter end.
- **No formula logic in TS or Excel.** The dashboard (Phase 2) and Excel export (Phase 4) read the `ratios` table only.
- **Post-CECL nomenclature.** ACL, never ALLL.

## What NOT to redo

- Don't re-ingest the 5 banks unless explicitly asked — they're already in Supabase. (Re-ingest is idempotent and now triggers the restatement detector, so it's not destructive; just unnecessary.)
- Don't re-apply the `suppress_when JSONB` migration — it's live.
- Don't recreate Day 1/2/3/4 artifacts (already committed).
- Don't use `--base` or `--uncommitted` with a PROMPT to `codex review` in CLI v0.131.0 — they're mutually exclusive. Stage first (`git add -A`) and call `codex review "$PROMPT"` with no diff flag.
- Don't trust the BOK cert (4862) or Cullen/Frost cert (5560) from the original plan — they're inactive. Use **4214** and **5510**.
- Don't bump handler `version="v1"` during Phase 1 — the contract test forbids it.

## Recommended first action

Read these three files in order before touching anything:
1. `/Users/connortipton/Projects/Peerbench/PLAN.md` — project plan v1.3
2. `/Users/connortipton/Projects/Peerbench/CLAUDE.md` — conventions
3. `/Users/connortipton/Projects/Peerbench/docs/divergences.md` — open items + methodology gaps

Then **verify the codebase + DB are in the expected clean state** — three quick checks:

```bash
# 1. Git: working tree clean, at bd52169 (or beyond)
git -C /Users/connortipton/Projects/Peerbench log --oneline -3
git -C /Users/connortipton/Projects/Peerbench status --short

# 2. Tests: should report "35 passed" with no skips
cd /Users/connortipton/Projects/Peerbench && uv run pytest 2>&1 | tail -3

# 3. Validation gate: should report "PASS" with mean <2 bps, max <5 bps
cd /Users/connortipton/Projects/Peerbench && \
  uv run peerbench validate --certs 4063,4214,110,11063,5510 --quarters 8 \
    --write-snapshot docs/validation-snapshot.md 2>&1 | tail -3
```

If any of those three diverge from the expected state, stop and surface to the user before doing substantive work — something landed between this handoff and now (FDIC restatement, manual edit, etc.).

Then ask the user what they want to do. Most likely menu:
- **(a)** Task 25: open plan-mode for FFIEC CDR ingest. Biggest remaining Phase 1 piece — unlocks `cet1` and `htm_loss_t1`.
- **(b)** Phase 2 kickoff: scaffold the Next.js 16 dashboard. Phase 1 data is ready and validated.
- **(c)** `top_loan_cat`: expand RC-C field ingest and implement the handler. Smaller chunk, can slot in before or alongside Task 25.

## User context / preferences (from memory)

- Connor, prepping for Summer 2026 FP&A internship at MidFirst Bank.
- Solo developer, fresh repo, this project doubles as portfolio material.
- High autonomy ("just go with your best recommendations") but wants a heads-up before live DB changes, pushes, or other irreversible actions.
- Prefers check-ins at chunk boundaries, not narration of every step.
- Reachable feedback signals: when shown a plan, picks an option or asks targeted clarifying questions rather than asking for more options.
