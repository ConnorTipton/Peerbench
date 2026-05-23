# Excel comp workbook export — design spec

**Phase:** 4.2
**Date:** 2026-05-23
**Owner:** Connor
**Status:** Draft for review

---

## Goal

Ship a CLI command that emits an FP&A-grade `.xlsx` comp workbook for a given
anchor bank and quarter, matching the dashboard's data exactly. The workbook
is the deliverable a banker can mark up in track changes and email around — it
is also the project's hosting-failure hedge (CLI works offline against the
local DB).

## Scope

- One CLI command: `peerbench export`.
- Six tabs: Cover, Summary, Comp Sheets (one per peer), Time Series (one per
  category), Restatement Log, Methodology.
- Reads from `ratios`, `facts`, `quality_log`, `ratio_defs`, `institutions`,
  `quarters`. No recomputation — values are read as stored. Per CLAUDE.md,
  the export layer is forbidden from formula logic.
- MidFirst (cert 4063) is the default anchor; any FDIC-insured active bank
  can be the anchor via `--anchor`.

### Non-goals (deferred)

- Multiple anchors in one workbook.
- Custom peer-set CLI flag (peers = `institutions.active = true`, same rule
  as the dashboard).
- Image embedding (logos, charts).
- Excel-native formulas — the workbook ships values only.
- PDF export.

---

## CLI surface

```
uv run peerbench export \
    --quarter 2025-Q4 \
    --output ./output/ \
    [--anchor 4063]
```

| Flag | Type | Default | Required | Notes |
| :--- | :--- | :--- | :--- | :--- |
| `--quarter` | `str` | — | yes | `YYYY-Qn` format. Validated against `quarters` table. |
| `--output` | `Path` | — | yes | Must be a directory. Created if missing. |
| `--anchor` | `int` | `4063` | no | FDIC cert. Validated against `institutions` (need not be `active`). |

**Output file:** `<output_dir>/peerbench_<anchor_cert>_<quarter_id>.xlsx`,
e.g. `./output/peerbench_4063_2025-Q4.xlsx`. Existing file is overwritten.

**Exit codes:**
- `0` — workbook written.
- `2` — bad inputs (unknown quarter, unknown anchor, `--output` is a file).

---

## Data flow

```
DB session ──► run_export(session, anchor_cert, quarter_id, out_dir)
                  │
                  ├─► build_cover(...)         → CoverTab
                  ├─► build_summary(...)        → SummaryTab
                  ├─► build_comp_sheets(...)    → list[CompSheetTab]
                  ├─► build_time_series(...)    → list[TimeSeriesTab]
                  ├─► build_restatement_log(...) → RestatementTab
                  └─► build_methodology(...)    → MethodologyTab
                          │
                          ▼
                  WorkbookBundle (typed dataclass)
                          │
                          ▼
                  write_workbook(bundle, out_path)  ← openpyxl lives only here
                          │
                          ▼
                  Path on disk
```

The split:
- **Builders** read DB rows, do all selection/aggregation/quartile math, and
  emit typed payloads. **Zero openpyxl imports.**
- **Writer** consumes typed payloads and writes the openpyxl file. **Zero DB
  imports.**

This makes data shape testable without an xlsx file, and openpyxl wiring
testable without a database.

---

## Module layout

```
src/peerbench/export/
  __init__.py                re-exports run_export
  workbook.py                run_export entry point + WorkbookBundle dataclass
  data/
    __init__.py
    types.py                 typed dataclasses for each tab payload
    cover.py                 build_cover
    summary.py               build_summary + quartile bucketing
    comp_sheet.py            build_comp_sheets + sheet-name sanitization
    time_series.py           build_time_series
    restatement.py           build_restatement_log + affected-ratios derivation
    methodology.py           build_methodology
  format.py                  percent / dollar / negative-parens formatters
  directions.py              Python mirror of web/lib/heatmap-directions.ts
  style.py                   openpyxl style constants
  writer.py                  write_workbook + per-tab writers
```

New top-level dir mirrors existing peerbench style (`src/peerbench/ingest/`,
`src/peerbench/ratio_engine/`).

---

## Tab specifications

### 1. Cover

Single sheet, no frozen panes. Plain text only (no images).

| Row | Content |
| :--- | :--- |
| 1 | "Peerbench — Bank Peer Benchmarking" (24pt bold) |
| 2 | "{Anchor name} · Cert {anchor_cert}" |
| 3 | "As of {quarter end date, e.g. December 31, 2025}" |
| 4 | (blank) |
| 5 | "Generated {UTC timestamp ISO 8601} from data ingested through {max(quarters.ingest_at, restricted to data in this workbook) date}" |
| 6 | (blank) |
| 7 | "Workbook contents:" (bold) |
| 8 | "• Summary — all 30 ratios, anchor + peers, latest quarter" (with cross-sheet hyperlink) |
| 9 | "• Comp Sheets — one tab per peer, side-by-side I/S + B/S + ratios" |
| 10 | "• Time Series — 8 quarters by ratio category" |
| 11 | "• Restatement Log — facts revised by FDIC affecting workbook ratios" |
| 12 | "• Methodology — formulas, sources, regulatory thresholds" |
| 13 | (blank) |
| 14 | "Data sources: FDIC BankFind API, FFIEC CDR bulk files." |
| 15 | "Restatements detected automatically; see Restatement Log tab." |

### 2. Summary

**Layout:** all 30 ratios for anchor + all active peers, latest quarter, with
peer median + anchor rank columns. One row per ratio, grouped by category
with section header rows.

**Columns:**

| Col | Header | Source |
| :--- | :--- | :--- |
| A | Category | `CATEGORY_LABELS[ratio_def.category]` (merged across rows of same category) |
| B | Ratio | `ratio_def.display_name` |
| C | Anchor (e.g. "MidFirst") | `ratios.value` for anchor cert |
| D…D+N-1 | Peer 1…Peer N (alpha) | `ratios.value` for each peer cert |
| D+N | Peer median | median of peer values (anchor excluded) for the row, ignoring suppressed |
| D+N+1 | Anchor rank | direction-aware rank of anchor within (anchor + peers), 1 = best |
| D+N+2 | Δ vs median | anchor − peer median, formatted as bps for percent ratios |

**Row 1 / Row 2 — column headers:**
- Row 1: institution name ("MidFirst" / each peer name), peer median /
  rank / Δ labels.
- Row 2: "Cert {n}" subtitle under each institution column; blank under
  median / rank / Δ.

**Section header rows:** one row per category (light gray fill, bold, merged
across all columns) immediately above the first ratio in that category. Order
follows `CATEGORY_ORDER`.

**Row order within each category:** matches `RATIO_ORDER` exactly.

**Direction-aware rank:**
- `higher_is_positive`: rank 1 = highest value.
- `higher_is_negative`: rank 1 = lowest value.
- `neutral`: rank cell is em-dash; ranks suppressed because they would be
  misleading.

**Quartile tinting on peer columns (C…D+N-1):**
- Top quartile (direction-aware): green `#E6F4EA`.
- Bottom quartile (direction-aware): red `#FCE8E6`.
- `neutral` direction: no quartile tint.
- Suppressed cells excluded from quartile cutoff calculation (mirrors
  dashboard, `web/lib/heatmap.ts`).

**Regulatory thresholds:**
- Amber tint `#FEF7E0` if value ≥ `amber_pct`.
- Red tint `#FBD5D1` if value ≥ `red_pct`.
- Precedence: red > amber > heatmap tint > anchor tint.

**Anchor row column (C):** navy tint `#E8EEF7` on all ratios (matches
dashboard accent /6%).

**Frozen panes:** freeze pane at C3 (row 1–2 stay locked, column A–B stay
locked when scrolling right).

**Number formats:** all percent cells `0.00%;(0.00%)`, rank cells integer,
em-dash on null.

### 3. Comp Sheets — one tab per peer

One tab per peer (anchor excluded — Comp Sheet IS the anchor-vs-one-peer
comparison). Tab name = peer institution name, truncated to 31 chars,
sanitized of invalid chars (`[]:*?/\`). On collision, append numeric suffix.

**Sheet layout (top to bottom):**

#### Section A: Income statement (4 quarters)

10 columns: line item | anchor Q-3 | anchor Q-2 | anchor Q-1 | anchor Q |
peer Q-3 | peer Q-2 | peer Q-1 | peer Q | Δ Q (anchor − peer current).
The four anchor columns and four peer columns each sit under a merged
"Anchor" / "Peer" header band.

Rows (7): Interest income (`INTINC`), Interest expense (`EINTEXP`),
Net interest income (`NIM`), Provision for credit losses (`ELNATR`),
Non-interest income (`NONII`), Non-interest expense (`NONIX`),
Net income (`NETINC`).

Pre-tax income deliberately omitted — FDIC's tracked YTD $ field set does
not expose a clean "income before income taxes" code (`IBEFTAX*` variants
are all qtly % international-ops series). The seven-line I/S still gives
the analyst the full revenue/expense waterfall.

All values read from `facts` (YTD as reported for the quarter); FFIEC
convention is thousands of dollars. `ELNATR` is the one code in this list
not yet tracked by the pipeline — the implementation plan adds it to
`INCOME_FIELDS` in `peerbench.fdic_fields` and backfills via `peerbench
ingest`.

#### Section B: Balance sheet (period-end, latest quarter)

4 columns: line item | anchor EOP | peer EOP | Δ.

Rows (7): Total assets (`ASSET`), Loans gross (`LNLSGR`), Securities
(`SC`), Cash & equivalents (`CHBAL`), Total deposits (`DEP`),
Total liabilities (`LIAB`), Total equity (`EQ`).

"Borrowings" deliberately replaced with Total liabilities — the project's
tracked field set has no single YTD $ "other borrowed money" code, and
deriving `LIAB − DEP` would cross the "no formula logic in export" line.
Total liabilities preserves the assets-vs-funding-vs-equity narrative the
analyst expects from a comp sheet.

TCE deliberately excluded — TCE/TA appears in the ratios block below;
including TCE as a line would require a derivation (`EQ − INTAN`), which
crosses the same line.

#### Section C: Ratios block

6 columns: ratio name | formula | anchor value | peer value | Δ (bps for
percent ratios) | direction note.

Rows: all 30 ratios in `RATIO_ORDER`, grouped by category with section
headers.

Formula column reads `ratio_defs.numerator_formula` /
`ratio_defs.denominator_formula` and renders as `numerator / denominator`.

Direction note column: "Higher better", "Lower better", "Neutral" from
`RATIO_DIRECTIONS`.

**Frozen panes:** row 3 (headers above the freeze).

### 4. Time Series — one tab per category

One tab per ratio category in `CATEGORY_ORDER` (7 tabs). Tab name from
`CATEGORY_LABELS`, sanitized + truncated to 31 chars.

**Layout per tab:** stacked blocks, one per ratio in that category. Between
blocks: one blank spacer row.

**Per-block layout:**

```
Net Interest Margin          ← row 1: bold, 14pt
Net interest income / Avg earning assets    ← row 2: formula text, 10pt italic
                2024-Q1  2024-Q2  ...  2025-Q4    ← row 3: quarter headers, bold
MidFirst         3.42%    3.51%        3.61%      ← row 4: anchor, navy tint
BOK Financial    3.18%    3.21%        3.30%      ← rows 5..N+3: peers alphabetical
...
                                                  ← blank spacer
Return on Assets
...
```

**Quartile tinting per quarter column:** same direction-aware rule as
Summary, computed per (ratio, quarter) across the visible peer set.

**8 quarters:** the latest 8 quarters available in `quarters` table where
ratios exist for the target ratio. Mirrors dashboard's `getRatioTimeSeries`
window.

**Frozen panes:** row 1 + column A (peer names always visible when
scrolling right across quarters).

### 5. Restatement Log

Single sheet.

**Source:** `quality_log` where `event_type = 'restated'`, joined to
`institutions` for bank name. Filtered to events where:
- The restated `(cert, field_code)` appears in any ratio's field dependency
  (via `web/lib/ratio-field-deps.generated.json` — already committed,
  generated by `peerbench export-field-deps`).
- The restated quarter is within the 8-quarter window covered by the Time
  Series tabs.

**Columns:**

| Col | Header | Source |
| :--- | :--- | :--- |
| A | Detected at | `quality_log.detected_at`, UTC date |
| B | Cert | `quality_log.cert` |
| C | Bank | `institutions.name` (joined) |
| D | Quarter | `quality_log.quarter_id` |
| E | Field code | `quality_log.field_code` |
| F | Old value | `quality_log.old_value`, formatted via `format_fact_value` (thousands suffix for dollar fields) |
| G | New value | `quality_log.new_value`, same formatter |
| H | Δ | `new_value − old_value`, same formatter |
| I | Affected ratios | comma-separated `ratio_id`s whose handler reads this field, from the field-deps snapshot |

**Sort:** detected_at DESC, then quarter_id DESC.

**Empty state:** if no rows match, render row 2 as "No restatements
affecting workbook ratios." (italic gray) and leave the rest blank.

**Frozen panes:** row 1.

### 6. Methodology

Single sheet. Two-section layout: a top "Notes" block, then per-ratio blocks
in `RATIO_ORDER`.

**Notes block (rows 1–15ish):**

- "Data sources: FDIC BankFind API + FFIEC CDR bulk files."
- "Annualization rule: YTD income × 4/Qn for Q1–Q3; Q4 not annualized."
- "Tax-equivalent: ratios reported on a non-TE basis. UBPR uses TE; expect
  5–15 bps gap on NIM/yields depending on muni mix."
- "Average vs period-end: per `ratio_defs.avg_or_eop`. AVG ratios use FDIC
  5-period YTD averages."
- "CBLR filers: small banks under the Community Bank Leverage Ratio
  framework do not report Tier 1 RBC / Total RBC / CET1. Those four cells
  render em-dash and are excluded from quartile cutoffs."
- "Restatement detector: incoming FDIC values are compared to stored
  values; on diff, the fact is flagged restated, logged, and affected
  ratios are recomputed. Forward-quarter ratios that depend on 5-period
  averages are also flagged partial."
- "Regulatory citations: SR 07-1, OCC Bulletin 2006-46, FIL-23-2023."

**Per-ratio block (one per ratio, in `RATIO_ORDER`):**

Two-column key/value layout:

| Row | Key | Value |
| :--- | :--- | :--- |
| 1 | (ratio display name as bold header, merged) | |
| 2 | Category | `ratio_def.category` (label form) |
| 3 | Formula | `numerator / denominator` |
| 4 | Source fields | from field-deps snapshot, comma-separated |
| 5 | Annualization | "YTD × 4/Qn" if `annualize` else "Not annualized" |
| 6 | Basis | `ratio_def.avg_or_eop` ("AVG" / "EOP") |
| 7 | FDIC pre-computed | `ratio_def.fdic_precomputed_code` or "—" |
| 8 | Regulatory threshold | rendered from `regulatory_threshold` JSONB if present, e.g. "Amber ≥ 300%, Red ≥ 400% — SR 07-1 §III.A" |
| 9 | Notes | `ratio_def.notes` |
| 10 | (blank spacer) | |

**Frozen panes:** row 1.

---

## Styling constants (`style.py`)

Centralized so a future Phase 4.3 design pass can re-tune the palette in one
place.

| Constant | Value | Use |
| :--- | :--- | :--- |
| `INPUT_BLUE` | `#1E40AF` | Font color for analyst-editable labels (anchor/peer names, headers) |
| `COMPUTED_BLACK` | `#000000` | Font color for computed cells (ratio values, deltas) |
| `HARDCODED_GREEN` | `#16A34A` | Font color for hardcoded constants in copy (e.g., regulatory threshold numerics in Methodology notes) |
| `HEADER_FILL` | `#0F172A` | Dark navy header row fill |
| `HEADER_FONT` | white | Header row font color |
| `SECTION_HEADER_FILL` | `#F1F5F9` | Light gray for category headers |
| `ANCHOR_TINT` | `#E8EEF7` | Navy tint for anchor row / column |
| `QUARTILE_TOP` | `#E6F4EA` | Top-quartile cell tint (direction-aware) |
| `QUARTILE_BOTTOM` | `#FCE8E6` | Bottom-quartile cell tint (direction-aware) |
| `THRESHOLD_AMBER` | `#FEF7E0` | Regulatory amber tint |
| `THRESHOLD_RED` | `#FBD5D1` | Regulatory red tint |
| `NUMFMT_PERCENT` | `0.00%;(0.00%)` | All ratio cells; negatives in parens |
| `NUMFMT_CURRENCY` | `$#,##0;($#,##0)` | I/S + B/S dollar cells |
| `NUMFMT_INTEGER` | `#,##0;(#,##0)` | Counts, rank |
| `BORDER_THIN` | thin gray | Every data cell |
| `FONT_BODY` | Calibri 11 | Default |
| `FONT_HEADER` | Calibri 11 bold | Header row |
| `FONT_TITLE` | Calibri 24 bold | Cover title |
| `FONT_RATIO_NAME` | Calibri 14 bold | Time-series block header |

Cell layer-precedence (mirrors dashboard `composeCellBg`): red > amber >
quartile > anchor tint > zebra (none in our case).

---

## Format helpers (`format.py`)

Python mirrors of `web/lib/format.ts`. Pure functions, no side effects.

```python
def format_ratio(value: Decimal | None) -> str | None: ...
    # Returns None if value is None (cell stays empty); else a string for
    # the displayed value. openpyxl applies NUMFMT_PERCENT separately so
    # this returns the raw float in [0, 1] range; em-dash handled by writer.

def format_fact_value(value: Decimal | None) -> str: ...
    # Restatement log: thousand-grouped integer; em-dash on None.

def format_delta_bps(anchor: Decimal | None, peer: Decimal | None) -> str: ...
    # Returns "+42 bps" / "(15 bps)" / em-dash. Used in Summary Δ column.
```

`format_ratio` returns numeric (not string) for cells so openpyxl can apply
the percent NumFmt; the em-dash case is handled by the writer leaving the
cell blank, which Excel renders as nothing. Considered putting a literal
em-dash string in null cells, but mixing string and number cells in one
column breaks Excel sorting. Blank is the right call.

---

## Directions table (`directions.py`)

```python
RATIO_DIRECTIONS: dict[str, Literal["higher_is_positive", "higher_is_negative", "neutral"]] = {
    "nim": "higher_is_positive",
    "roa": "higher_is_positive",
    ...
}
```

Manually maintained to mirror `web/lib/heatmap-directions.ts`. A contract
test parses the TS source (string literal extraction, not import) and
asserts 1:1 correspondence. Drift fails CI loudly. Pattern matches
`tests/contract/test_ratio_registry.py` for `ratio_defs` ↔ handlers.

---

## Error handling

| Scenario | Behavior |
| :--- | :--- |
| `--quarter` unknown | Exit 2, message lists 8 most-recent known quarters |
| `--anchor` unknown | Exit 2, message names the cert and suggests `peerbench info` |
| `--output` is a file path, not a directory | Exit 2 |
| `--output` directory missing | Created (parents=True, exist_ok=True) |
| Output file already exists | Overwritten silently (export is idempotent) |
| Anchor has zero ratios for the quarter | Workbook still generated; cells em-dash; Cover note added: "Anchor has no ratios for {quarter}." |
| Zero active peers (anchor only) | Workbook generated with no peer columns / no Comp Sheet tabs; Cover warning |
| Peer suppressed for a ratio (CBLR, missing fact) | Em-dash; excluded from quartile cutoff |
| Ratio has no field-deps entry (e.g., `top_loan_cat` raises `NotImplementedError`) | Methodology block still rendered; Source fields cell reads "—"; ratio absent from Restatement Log "affected" derivation |

---

## Testing

### Unit tests (`tests/unit/test_export_*.py`)

| File | Coverage |
| :--- | :--- |
| `test_format.py` | percent formatting, dollar formatting, negative parens, delta-bps |
| `test_summary_data.py` | direction-aware rank, quartile bucketing with suppressed cells excluded, anchor pinning, anchor-row tint flag |
| `test_comp_sheet_data.py` | sheet-name sanitization (31-char limit, invalid chars `[]:*?/\`, collision suffix), I/S column ordering, B/S row ordering |
| `test_time_series_data.py` | block order = `RATIO_ORDER`, anchor pinned at row 4, 8-quarter window, peer alpha sort, missing-quarter em-dash |
| `test_restatement_data.py` | filter on event_type='restated', affected-ratios derivation via field-deps JSON, sort order, empty-state row |
| `test_methodology_data.py` | every ratio in `RATIO_ORDER` produces a block, regulatory_threshold JSONB rendering |

Builders take SQLAlchemy `Session` but unit tests bypass DB by passing
in-memory dataclass fixtures (mirror the existing pattern in
`tests/unit/test_validate.py`).

### Integration test (`tests/integration/test_export_workbook.py`)

Marked `@pytest.mark.integration`, skipped by default in CI without DB
credentials. Test:

1. Seed an in-memory SQLite DB with: 5 institutions (1 anchor + 4 peers),
   2 quarters of facts + ratios, 1 quality_log restatement.
2. Run `run_export(session, anchor_cert=4063, quarter_id="2025-Q4", out_dir=tmp_path)`.
3. Open the resulting `.xlsx` with `openpyxl.load_workbook(read_only=False)`.
4. Assert:
   - 6 + N tabs exist (Cover, Summary, N peer comp sheets, 7 time-series
     tabs, Restatement Log, Methodology).
   - Summary cell `C4` (anchor first-ratio) is a numeric value.
   - Summary header row freeze pane = `"C3"`.
   - Summary `C4` `number_format == "0.00%;(0.00%)"`.
   - At least one cell carries `QUARTILE_TOP` fill on the test data.
   - Restatement Log row 2 has the seeded restatement.
   - Methodology has 30 ratio-name header rows.

Catches both data-shape bugs and openpyxl-wiring bugs (number formats,
frozen panes, fills). One real round-trip is worth more than ten unit
tests on the writer.

### Contract tests (`tests/contract/`)

| File | Coverage |
| :--- | :--- |
| `test_export_directions_mirror.py` | parses `web/lib/heatmap-directions.ts` and diffs against Python `RATIO_DIRECTIONS` (1:1 keys, identical values) |
| `test_export_methodology_completeness.py` | every ratio in `RATIO_ORDER` has a methodology block; every methodology block has a corresponding `ratio_defs` row |

---

## Definition of done

- `uv run peerbench export --quarter 2025-Q4 --output ./output/` produces
  `peerbench_4063_2025-Q4.xlsx` with all 6 tab kinds.
- Summary tab values match the dashboard's matrix exactly for the same
  quarter (visual spot-check + automated cell-level diff in a dev script).
- Restatement Log shows the same 5 restatement markers that the dashboard
  surfaces on 2025-Q4.
- Conditional formatting renders correctly when the file is opened in
  Excel for Mac (the target FP&A platform).
- `uv run pytest tests/unit/test_export_*.py` green.
- `uv run pytest tests/integration/test_export_workbook.py` green locally.
- `uv run pytest tests/contract/test_export_*.py` green.
- `ruff format`, `ruff check`, `pyright --strict` green on
  `src/peerbench/export/`.
- Reviewer subagent gate pass before merge.

---

## Open follow-ups

Tracked separately for Phase 4.3 or the implementation plan, not blocking:

1. **FDIC field codes for I/S + B/S** — verified against
   `data/fdic_field_reference.csv` during spec self-review. I/S uses
   `INTINC, EINTEXP, NIM, ELNATR, NONII, NONIX, NETINC`; B/S uses
   `ASSET, LNLSGR, SC, CHBAL, DEP, LIAB, EQ`. `ELNATR` is the one code
   missing from `INCOME_FIELDS` today; the implementation plan adds it
   and re-ingests.
2. **Plain-English ratio meaning column** — Comp Sheet ratios block ships
   *without* the plain-English column to keep scope tight. Add later by
   either a new `ratio_defs.plain_english` schema column or a const map
   in the export module. Belongs in Phase 4.1 alongside the `/insight`
   skill, which is the same vocabulary.
3. **Methodology cross-sheet hyperlinks from Cover** — implementation
   detail; openpyxl supports `Hyperlink` with `target="#'Methodology'!A1"`.
   Not blocking, but a nice polish.
4. **Time Series tab for `top_loan_cat`** — that ratio has no values
   (handler raises `NotImplementedError`); its time-series block will be
   an all-em-dash table. Acceptable for v1 — the methodology block makes
   the absence explicit. Drop the block entirely if it looks like noise.
5. **Excel for Windows compatibility** — primary target is Excel for Mac
   (Connor's machine and MidFirst's standard). Windows compatibility is
   expected to work out of the box with openpyxl but not formally
   verified.
