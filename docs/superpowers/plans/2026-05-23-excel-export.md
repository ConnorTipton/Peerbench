# Excel comp workbook export — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `uv run peerbench export --quarter YYYY-Qn --output ./output/` — a CLI command that emits a six-tab `.xlsx` comp workbook matching the dashboard's data, per Phase 4.2 of `PLAN.md` v1.3.

**Architecture:** Pure-function builders consume a SQLAlchemy session and emit typed dataclasses (`SummaryTab`, `CompSheetTab`, etc.). A single writer module consumes the bundle and writes the openpyxl file. No formula logic in the export layer — values come from `ratios`; raw FFIEC line items come from `facts`.

**Tech Stack:** Python 3.13, openpyxl 3.1, SQLAlchemy 2.x, Typer (existing CLI). New `peerbench.export` sub-package. Pyright strict, ruff format.

**Spec:** `docs/superpowers/specs/2026-05-23-excel-export-design.md` (committed at `d7a5b97`).

---

## File structure

```
src/peerbench/export/
  __init__.py                 # re-exports run_export
  workbook.py                 # run_export entry + WorkbookBundle dataclass
  format.py                   # percent / dollar / delta-bps formatters
  directions.py               # Python mirror of web/lib/heatmap-directions.ts
  quartile.py                 # Python mirror of web/lib/heatmap.ts quartile + bucket
  style.py                    # openpyxl style constants
  writer.py                   # write_workbook + per-tab writers
  data/
    __init__.py
    types.py                  # typed dataclasses for tab payloads
    cover.py                  # build_cover
    summary.py                # build_summary (rank + quartile + anchor)
    comp_sheet.py             # build_comp_sheets + sheet-name sanitization
    time_series.py            # build_time_series (8-quarter window)
    restatement.py            # build_restatement_log
    methodology.py            # build_methodology

tests/unit/
  test_export_format.py
  test_export_directions.py
  test_export_quartile.py
  test_export_cover.py
  test_export_methodology.py
  test_export_restatement.py
  test_export_summary.py
  test_export_comp_sheet.py
  test_export_time_series.py

tests/contract/
  test_export_directions_mirror.py
  test_export_methodology_completeness.py

tests/integration/
  test_export_workbook.py     # round-trip a real .xlsx
```

Files that change outside `peerbench.export`:
- `src/peerbench/fdic_fields.py` — append `ELNATR` to `INCOME_FIELDS`.
- `src/peerbench/cli.py` — register the new `export` Typer command.

---

## Task 1: Package skeleton + typed payloads

**Files:**
- Create: `src/peerbench/export/__init__.py`
- Create: `src/peerbench/export/data/__init__.py`
- Create: `src/peerbench/export/data/types.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_export_types.py`:

```python
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from peerbench.export.data.types import (
    CoverTab,
    SummaryRow,
    SummaryTab,
    WorkbookBundle,
)


def test_workbook_bundle_holds_six_tab_kinds() -> None:
    cover = CoverTab(
        anchor_cert=4063,
        anchor_name="MidFirst",
        quarter_id="2025-Q4",
        quarter_end="December 31, 2025",
        generated_at=datetime(2026, 5, 23, 12, 0, 0),
        data_vintage="2026-05-22",
        notes=[],
    )
    summary = SummaryTab(
        institution_columns=[(4063, "MidFirst")],
        rows=[
            SummaryRow(
                ratio_id="nim",
                display_name="Net Interest Margin",
                category="profitability",
                anchor_value=Decimal("0.034"),
                peer_values={},
                peer_median=None,
                anchor_rank=1,
                delta_vs_median=None,
                direction="higher_is_positive",
                amber_pct=None,
                red_pct=None,
            )
        ],
    )
    bundle = WorkbookBundle(
        cover=cover,
        summary=summary,
        comp_sheets=[],
        time_series=[],
        restatement_log=None,
        methodology=None,
    )
    assert bundle.cover.anchor_cert == 4063
    assert bundle.summary.rows[0].ratio_id == "nim"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_export_types.py -v`
Expected: FAIL with `ModuleNotFoundError: peerbench.export`.

- [ ] **Step 3: Write minimal implementation**

`src/peerbench/export/__init__.py`:

```python
"""Phase 4.2 — Excel comp workbook export.

Pure-function builders emit typed payloads; a single writer module owns
openpyxl. No formula logic in this layer — values are read from `ratios`
and raw line items from `facts`. See
docs/superpowers/specs/2026-05-23-excel-export-design.md.
"""

from peerbench.export.workbook import run_export

__all__ = ["run_export"]
```

`src/peerbench/export/data/__init__.py`:

```python
"""Pure-function data builders for each Excel tab. No openpyxl imports."""
```

`src/peerbench/export/data/types.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Literal

Direction = Literal["higher_is_positive", "higher_is_negative", "neutral"]
DataQuality = Literal["ok", "partial", "suppressed", "mismatch"]


@dataclass(frozen=True, slots=True)
class CoverTab:
    anchor_cert: int
    anchor_name: str
    quarter_id: str
    quarter_end: str
    generated_at: datetime
    data_vintage: str
    notes: list[str]


@dataclass(frozen=True, slots=True)
class SummaryRow:
    ratio_id: str
    display_name: str
    category: str
    anchor_value: Decimal | None
    peer_values: dict[int, Decimal | None]  # cert -> value (None if suppressed/missing)
    peer_median: Decimal | None
    anchor_rank: int | None  # 1 = best; None for neutral direction
    delta_vs_median: Decimal | None  # anchor - median, raw fraction
    direction: Direction
    amber_pct: Decimal | None  # regulatory threshold, fraction (3.0 = 300%)
    red_pct: Decimal | None


@dataclass(frozen=True, slots=True)
class SummaryTab:
    institution_columns: list[tuple[int, str]]  # [(cert, name), ...] anchor first
    rows: list[SummaryRow]


@dataclass(frozen=True, slots=True)
class IncomeStatementLine:
    label: str
    field_code: str
    anchor_values: list[Decimal | None]  # 4 quarters, oldest first
    peer_values: list[Decimal | None]


@dataclass(frozen=True, slots=True)
class BalanceSheetLine:
    label: str
    field_code: str
    anchor_value: Decimal | None
    peer_value: Decimal | None


@dataclass(frozen=True, slots=True)
class CompRatioRow:
    ratio_id: str
    display_name: str
    category: str
    formula: str
    anchor_value: Decimal | None
    peer_value: Decimal | None
    direction: Direction


@dataclass(frozen=True, slots=True)
class CompSheetTab:
    sheet_name: str  # already sanitized + truncated
    peer_cert: int
    peer_name: str
    anchor_cert: int
    anchor_name: str
    quarter_id: str
    income_statement_quarters: list[str]  # e.g. ['2025-Q1', '2025-Q2', '2025-Q3', '2025-Q4']
    income_statement: list[IncomeStatementLine]
    balance_sheet: list[BalanceSheetLine]
    ratios: list[CompRatioRow]


@dataclass(frozen=True, slots=True)
class TimeSeriesPoint:
    cert: int
    value: Decimal | None


@dataclass(frozen=True, slots=True)
class TimeSeriesBlock:
    ratio_id: str
    display_name: str
    formula: str
    direction: Direction
    quarter_ids: list[str]  # 8 quarters, oldest first
    rows: list[tuple[int, str, list[Decimal | None]]]
    # rows: [(cert, institution_name, values_by_quarter)], anchor first


@dataclass(frozen=True, slots=True)
class TimeSeriesTab:
    sheet_name: str
    category: str  # e.g. "profitability"
    category_label: str  # e.g. "Profitability"
    blocks: list[TimeSeriesBlock]


@dataclass(frozen=True, slots=True)
class RestatementRow:
    detected_at: datetime
    cert: int
    bank_name: str
    quarter_id: str
    field_code: str
    old_value: Decimal | None
    new_value: Decimal | None
    affected_ratios: list[str]


@dataclass(frozen=True, slots=True)
class RestatementTab:
    rows: list[RestatementRow]


@dataclass(frozen=True, slots=True)
class MethodologyNote:
    label: str
    text: str


@dataclass(frozen=True, slots=True)
class MethodologyBlock:
    ratio_id: str
    display_name: str
    category: str
    formula: str
    source_fields: list[str]
    annualization: str
    basis: str  # "AVG" or "EOP"
    fdic_precomputed: str | None
    regulatory_threshold: str | None
    notes: str | None


@dataclass(frozen=True, slots=True)
class MethodologyTab:
    intro_notes: list[MethodologyNote]
    blocks: list[MethodologyBlock]


@dataclass(frozen=True, slots=True)
class WorkbookBundle:
    cover: CoverTab
    summary: SummaryTab
    comp_sheets: list[CompSheetTab]
    time_series: list[TimeSeriesTab]
    restatement_log: RestatementTab | None
    methodology: MethodologyTab | None
```

Also create a workbook.py stub so the `from peerbench.export.workbook import run_export` line in `__init__.py` resolves:

`src/peerbench/export/workbook.py`:

```python
"""Workbook orchestration. Filled in by later tasks."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session


def run_export(
    session: Session,
    *,
    anchor_cert: int,
    quarter_id: str,
    out_dir: Path,
) -> Path:
    raise NotImplementedError("filled in by Task 14")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_export_types.py -v`
Expected: PASS.

- [ ] **Step 5: Type-check**

Run: `uv run pyright src/peerbench/export`
Expected: 0 errors.

- [ ] **Step 6: Commit**

```bash
git add src/peerbench/export tests/unit/test_export_types.py
git commit -m "feat(export): Phase 4.2 scaffold — package skeleton + typed payloads"
```

---

## Task 2: format.py — percent / dollar / delta-bps helpers

**Files:**
- Create: `src/peerbench/export/format.py`
- Create: `tests/unit/test_export_format.py`

- [ ] **Step 1: Write the failing test**

```python
from __future__ import annotations

from decimal import Decimal

from peerbench.export.format import (
    EM_DASH,
    format_delta_bps,
    format_fact_value,
    format_ratio_for_cell,
)


def test_format_ratio_for_cell_returns_float_for_openpyxl() -> None:
    assert format_ratio_for_cell(Decimal("0.0342")) == 0.0342


def test_format_ratio_for_cell_none_returns_none() -> None:
    # openpyxl renders None as blank — better than mixing strings into a
    # numeric column (would break sort).
    assert format_ratio_for_cell(None) is None


def test_format_fact_value_thousands() -> None:
    # FFIEC values are stored in thousands; the formatter renders them
    # to whole dollars for the Restatement Log "old/new value" columns.
    assert format_fact_value(Decimal("1234567")) == "1,234,567"


def test_format_fact_value_none() -> None:
    assert format_fact_value(None) == EM_DASH


def test_format_fact_value_negative_parens() -> None:
    assert format_fact_value(Decimal("-500")) == "(500)"


def test_format_delta_bps_positive() -> None:
    # Anchor 3.50%, peer median 3.20% → +30 bps.
    assert format_delta_bps(Decimal("0.0350"), Decimal("0.0320")) == "+30 bps"


def test_format_delta_bps_negative() -> None:
    assert format_delta_bps(Decimal("0.0320"), Decimal("0.0350")) == "(30 bps)"


def test_format_delta_bps_none() -> None:
    assert format_delta_bps(None, Decimal("0.05")) == EM_DASH
    assert format_delta_bps(Decimal("0.05"), None) == EM_DASH
    assert format_delta_bps(None, None) == EM_DASH


def test_format_delta_bps_rounds_to_nearest_basis_point() -> None:
    # 0.005% → 5 bps; sub-bp deltas round to zero, not displayed as empty.
    assert format_delta_bps(Decimal("0.00500"), Decimal("0")) == "+50 bps"
    assert format_delta_bps(Decimal("0.000049"), Decimal("0")) == "+0 bps"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_export_format.py -v`
Expected: FAIL with `ModuleNotFoundError: peerbench.export.format`.

- [ ] **Step 3: Write minimal implementation**

```python
from __future__ import annotations

from decimal import Decimal

EM_DASH = "—"


def format_ratio_for_cell(value: Decimal | None) -> float | None:
    """Convert a stored ratio (fraction) to a float for an openpyxl cell.

    The cell's number_format ("0.00%;(0.00%)") handles the percent + parens
    display; passing None leaves the cell blank, which avoids mixing strings
    into a numeric column (which would break Excel sorting).
    """
    if value is None:
        return None
    return float(value)


def format_fact_value(value: Decimal | None) -> str:
    """Render a Call Report dollar value (in thousands) as a grouped integer.

    Negatives in parentheses; None as em-dash. Used by the Restatement Log
    tab where mixing string and numeric cells is acceptable because the
    column is unambiguously text.
    """
    if value is None:
        return EM_DASH
    if value < 0:
        return f"({format(abs(value), ',.0f')})"
    return format(value, ",.0f")


def format_delta_bps(anchor: Decimal | None, peer: Decimal | None) -> str:
    """Return anchor minus peer as a basis-point delta string.

    Used by the Summary tab Δ-vs-median column and the Comp Sheet ratios
    block. Both inputs must be fractions (0.034 = 3.4%); output is a
    formatted string ("+30 bps" / "(30 bps)" / em-dash).
    """
    if anchor is None or peer is None:
        return EM_DASH
    delta = anchor - peer
    bps = int((delta * Decimal(10000)).quantize(Decimal("1")))
    if bps < 0:
        return f"({abs(bps)} bps)"
    return f"+{bps} bps"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_export_format.py -v`
Expected: PASS (9 tests).

- [ ] **Step 5: Commit**

```bash
git add src/peerbench/export/format.py tests/unit/test_export_format.py
git commit -m "feat(export): format helpers — percent / fact / delta-bps"
```

---

## Task 3: quartile.py — direction-aware quartile bucketing

**Files:**
- Create: `src/peerbench/export/quartile.py`
- Create: `tests/unit/test_export_quartile.py`

This is a Python mirror of `web/lib/heatmap.ts`. Same Type-7 quantile algorithm, same `MIN_VALUES_FOR_QUARTILES = 4` threshold, same `excludes suppressed cells` rule.

- [ ] **Step 1: Write the failing test**

```python
from __future__ import annotations

from decimal import Decimal

from peerbench.export.quartile import (
    Bucket,
    QuartileCutoffs,
    bucket_for_cell,
    compute_quartile_cutoffs,
)


def test_compute_cutoffs_canonical_five_values() -> None:
    cutoffs = compute_quartile_cutoffs(
        [Decimal(v) for v in (10, 20, 30, 40, 50)]
    )
    assert cutoffs is not None
    assert cutoffs.q1 == Decimal(20)
    assert cutoffs.median == Decimal(30)
    assert cutoffs.q3 == Decimal(40)


def test_compute_cutoffs_returns_none_with_three_values() -> None:
    # MIN_VALUES_FOR_QUARTILES = 4. Fewer values → no cutoffs.
    assert compute_quartile_cutoffs([Decimal(1), Decimal(2), Decimal(3)]) is None


def test_compute_cutoffs_drops_nones() -> None:
    cutoffs = compute_quartile_cutoffs(
        [Decimal(10), None, Decimal(20), Decimal(30), Decimal(40), Decimal(50)]
    )
    assert cutoffs is not None
    assert cutoffs.median == Decimal(30)


def test_bucket_top_for_higher_is_positive() -> None:
    cutoffs = QuartileCutoffs(q1=Decimal(20), median=Decimal(30), q3=Decimal(40))
    assert bucket_for_cell(Decimal(50), cutoffs, "higher_is_positive") == "top"


def test_bucket_bottom_for_higher_is_positive() -> None:
    cutoffs = QuartileCutoffs(q1=Decimal(20), median=Decimal(30), q3=Decimal(40))
    assert bucket_for_cell(Decimal(10), cutoffs, "higher_is_positive") == "bottom"


def test_bucket_inverted_for_higher_is_negative() -> None:
    # Efficiency ratio: high value = bad → top quartile gets "bottom" tint.
    cutoffs = QuartileCutoffs(q1=Decimal(20), median=Decimal(30), q3=Decimal(40))
    assert bucket_for_cell(Decimal(50), cutoffs, "higher_is_negative") == "bottom"
    assert bucket_for_cell(Decimal(10), cutoffs, "higher_is_negative") == "top"


def test_bucket_neutral_returns_none() -> None:
    cutoffs = QuartileCutoffs(q1=Decimal(20), median=Decimal(30), q3=Decimal(40))
    assert bucket_for_cell(Decimal(50), cutoffs, "neutral") == "none"


def test_bucket_value_equal_to_q3_is_middle() -> None:
    # Strictly greater than q3 to be top; equality is middle. Matches TS.
    cutoffs = QuartileCutoffs(q1=Decimal(20), median=Decimal(30), q3=Decimal(40))
    assert bucket_for_cell(Decimal(40), cutoffs, "higher_is_positive") == "middle"


def test_bucket_none_value() -> None:
    cutoffs = QuartileCutoffs(q1=Decimal(20), median=Decimal(30), q3=Decimal(40))
    assert bucket_for_cell(None, cutoffs, "higher_is_positive") == "none"


def test_bucket_none_cutoffs() -> None:
    assert bucket_for_cell(Decimal(50), None, "higher_is_positive") == "none"


def test_direction_aware_rank_higher_is_positive() -> None:
    # Tested indirectly through the bucket; direction inversion is also
    # used by summary.py for rank. Skip dedicated test here; summary tests
    # cover it.
    pass
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_export_quartile.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

Direction = Literal["higher_is_positive", "higher_is_negative", "neutral"]
Bucket = Literal["top", "middle", "bottom", "none"]

MIN_VALUES_FOR_QUARTILES = 4


@dataclass(frozen=True, slots=True)
class QuartileCutoffs:
    q1: Decimal
    median: Decimal
    q3: Decimal


def compute_quartile_cutoffs(
    values: list[Decimal | None],
) -> QuartileCutoffs | None:
    """Type-7 quantile cutoffs over non-None values.

    Mirrors web/lib/heatmap.ts. Returns None if fewer than
    MIN_VALUES_FOR_QUARTILES distinct numeric values are present.
    """
    filtered = [v for v in values if v is not None]
    if len(filtered) < MIN_VALUES_FOR_QUARTILES:
        return None
    sorted_values = sorted(filtered)
    return QuartileCutoffs(
        q1=_quantile(sorted_values, Decimal("0.25")),
        median=_quantile(sorted_values, Decimal("0.5")),
        q3=_quantile(sorted_values, Decimal("0.75")),
    )


def _quantile(sorted_values: list[Decimal], q: Decimal) -> Decimal:
    n = len(sorted_values)
    idx = (Decimal(n) - 1) * q
    lo = int(idx)
    hi_dec = idx - Decimal(lo)
    if hi_dec == 0:
        return sorted_values[lo]
    return sorted_values[lo] + (sorted_values[lo + 1] - sorted_values[lo]) * hi_dec


def bucket_for_cell(
    value: Decimal | None,
    cutoffs: QuartileCutoffs | None,
    direction: Direction,
) -> Bucket:
    """Top / middle / bottom / none — direction-aware.

    `top` means a green tint should be drawn; `bottom` means red. For
    higher-is-positive ratios, a numeric top quartile is "top". For
    higher-is-negative ratios, the bucket is inverted (high efficiency
    ratio → "bottom" tint).
    """
    if value is None or cutoffs is None or direction == "neutral":
        return "none"
    if value > cutoffs.q3:
        return "top" if direction == "higher_is_positive" else "bottom"
    if value < cutoffs.q1:
        return "bottom" if direction == "higher_is_positive" else "top"
    return "middle"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_export_quartile.py -v`
Expected: PASS (10 tests).

- [ ] **Step 5: Commit**

```bash
git add src/peerbench/export/quartile.py tests/unit/test_export_quartile.py
git commit -m "feat(export): direction-aware quartile bucketing (Python mirror of heatmap.ts)"
```

---

## Task 4: directions.py + contract test against TS source

**Files:**
- Create: `src/peerbench/export/directions.py`
- Create: `tests/unit/test_export_directions.py`
- Create: `tests/contract/test_export_directions_mirror.py`

- [ ] **Step 1: Write the failing test (unit + contract)**

`tests/unit/test_export_directions.py`:

```python
from __future__ import annotations

from peerbench.export.directions import RATIO_DIRECTIONS, direction_for


def test_nim_is_higher_is_positive() -> None:
    assert direction_for("nim") == "higher_is_positive"


def test_eff_ratio_is_higher_is_negative() -> None:
    assert direction_for("eff_ratio") == "higher_is_negative"


def test_loans_assets_is_neutral() -> None:
    assert direction_for("loans_assets") == "neutral"


def test_unknown_ratio_defaults_to_neutral() -> None:
    assert direction_for("does_not_exist") == "neutral"


def test_thirty_ratios_covered() -> None:
    # 30 ratios in RATIO_ORDER (web/lib/ratio-order.ts) → 30 here.
    # Verified more strictly by the contract test, but a unit-level smoke
    # check catches an obvious omission.
    assert len(RATIO_DIRECTIONS) == 30
```

`tests/contract/test_export_directions_mirror.py`:

```python
"""Contract: peerbench.export.directions.RATIO_DIRECTIONS must mirror
web/lib/heatmap-directions.ts verbatim.

The TS file is the canonical source — it backs the dashboard's heat map.
The Python copy backs the Excel export. Both must agree on direction for
every ratio in RATIO_ORDER.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from peerbench.export.directions import RATIO_DIRECTIONS

REPO_ROOT = Path(__file__).resolve().parents[2]
TS_PATH = REPO_ROOT / "web" / "lib" / "heatmap-directions.ts"

# Matches:  ratio_id: "higher_is_positive",
LINE_RE = re.compile(
    r'^\s*([a-z_][a-z0-9_]*):\s*"(higher_is_positive|higher_is_negative|neutral)"',
    re.MULTILINE,
)


@pytest.mark.contract
def test_directions_mirror_matches_typescript_source() -> None:
    text = TS_PATH.read_text(encoding="utf-8")
    ts_entries = dict(LINE_RE.findall(text))
    assert ts_entries, "regex failed to extract entries from heatmap-directions.ts"
    py_entries = dict(RATIO_DIRECTIONS)

    only_in_py = set(py_entries) - set(ts_entries)
    only_in_ts = set(ts_entries) - set(py_entries)
    mismatched = {
        k: (py_entries[k], ts_entries[k])
        for k in set(py_entries) & set(ts_entries)
        if py_entries[k] != ts_entries[k]
    }

    assert not only_in_py, f"Python has extra: {only_in_py}"
    assert not only_in_ts, f"TS has entries Python is missing: {only_in_ts}"
    assert not mismatched, f"direction mismatches: {mismatched}"
```

- [ ] **Step 2: Run both tests, watch them fail**

Run: `uv run pytest tests/unit/test_export_directions.py tests/contract/test_export_directions_mirror.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write the implementation**

`src/peerbench/export/directions.py`:

```python
"""Per-ratio heat-map direction lookup.

Mirrors web/lib/heatmap-directions.ts verbatim. The contract test in
tests/contract/test_export_directions_mirror.py parses the TS source and
fails CI if either side drifts.
"""

from __future__ import annotations

from typing import Literal

Direction = Literal["higher_is_positive", "higher_is_negative", "neutral"]

RATIO_DIRECTIONS: dict[str, Direction] = {
    # Profitability.
    "nim": "higher_is_positive",
    "roa": "higher_is_positive",
    "roe": "higher_is_positive",
    "eff_ratio": "higher_is_negative",
    "ppnr_assets": "higher_is_positive",
    # Yields & costs.
    "yield_ea": "higher_is_positive",
    "cost_funds": "higher_is_negative",
    "nis": "higher_is_positive",
    # Balance sheet mix.
    "loans_deposits": "neutral",
    "loans_assets": "neutral",
    "sec_assets": "neutral",
    "cash_assets": "neutral",
    "deposits_liab": "neutral",
    "nonint_inc_rev": "higher_is_positive",
    "nonint_exp_assets": "higher_is_negative",
    "tce_ta": "higher_is_positive",
    # Asset quality.
    "npl_ratio": "higher_is_negative",
    "nco_ratio": "higher_is_negative",
    "acl_loans": "neutral",
    "acl_npl": "higher_is_positive",
    # Capital.
    "tier1_lev": "higher_is_positive",
    "tier1_rbc": "higher_is_positive",
    "total_rbc": "higher_is_positive",
    "cet1": "higher_is_positive",
    # Concentration.
    "cre_rbc": "neutral",
    "cd_rbc": "neutral",
    "top_loan_cat": "higher_is_negative",
    # Liquidity & deposit composition.
    "uninsured_dep": "higher_is_negative",
    "brokered_dep": "higher_is_negative",
    "htm_loss_t1": "higher_is_negative",
}


def direction_for(ratio_id: str) -> Direction:
    return RATIO_DIRECTIONS.get(ratio_id, "neutral")
```

- [ ] **Step 4: Run tests to verify pass**

Run: `uv run pytest tests/unit/test_export_directions.py tests/contract/test_export_directions_mirror.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add src/peerbench/export/directions.py tests/unit/test_export_directions.py tests/contract/test_export_directions_mirror.py
git commit -m "feat(export): direction lookup + contract test against TS source"
```

---

## Task 5: style.py — openpyxl style constants

**Files:**
- Create: `src/peerbench/export/style.py`

No new unit tests — these are constants. Indirectly verified by the integration test in Task 16.

- [ ] **Step 1: Write the file**

```python
"""openpyxl style constants for the Excel comp workbook export.

Centralized so a future Phase 4.3 design pass can re-tune the palette in
one place. Names mirror docs/design.md conventions where reasonable.
"""

from __future__ import annotations

from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

# --- Colors --------------------------------------------------------------

# Banker convention (used in Methodology hardcoded constants only).
INPUT_BLUE = "1E40AF"
HARDCODED_GREEN = "16A34A"

# Header band.
HEADER_FILL_HEX = "0F172A"
HEADER_FONT_HEX = "FFFFFF"
SECTION_HEADER_FILL_HEX = "F1F5F9"

# Cell tints (use color-mixed light variants so values stay readable).
ANCHOR_TINT_HEX = "E8EEF7"
QUARTILE_TOP_HEX = "E6F4EA"
QUARTILE_BOTTOM_HEX = "FCE8E6"
THRESHOLD_AMBER_HEX = "FEF7E0"
THRESHOLD_RED_HEX = "FBD5D1"

# --- Number formats ------------------------------------------------------

NUMFMT_PERCENT = "0.00%;(0.00%)"
NUMFMT_CURRENCY = "$#,##0;($#,##0)"
NUMFMT_INTEGER = "#,##0;(#,##0)"

# --- Fonts ---------------------------------------------------------------

FONT_BODY = Font(name="Calibri", size=11)
FONT_BODY_BOLD = Font(name="Calibri", size=11, bold=True)
FONT_HEADER = Font(name="Calibri", size=11, bold=True, color=HEADER_FONT_HEX)
FONT_SECTION_HEADER = Font(name="Calibri", size=11, bold=True)
FONT_TITLE = Font(name="Calibri", size=24, bold=True)
FONT_RATIO_NAME = Font(name="Calibri", size=14, bold=True)
FONT_FORMULA_ITALIC = Font(name="Calibri", size=10, italic=True, color="64748B")

# --- Fills ---------------------------------------------------------------

FILL_HEADER = PatternFill(fill_type="solid", fgColor=HEADER_FILL_HEX)
FILL_SECTION_HEADER = PatternFill(fill_type="solid", fgColor=SECTION_HEADER_FILL_HEX)
FILL_ANCHOR = PatternFill(fill_type="solid", fgColor=ANCHOR_TINT_HEX)
FILL_QUARTILE_TOP = PatternFill(fill_type="solid", fgColor=QUARTILE_TOP_HEX)
FILL_QUARTILE_BOTTOM = PatternFill(fill_type="solid", fgColor=QUARTILE_BOTTOM_HEX)
FILL_THRESHOLD_AMBER = PatternFill(fill_type="solid", fgColor=THRESHOLD_AMBER_HEX)
FILL_THRESHOLD_RED = PatternFill(fill_type="solid", fgColor=THRESHOLD_RED_HEX)

# --- Borders -------------------------------------------------------------

THIN_GRAY = Side(border_style="thin", color="CBD5E1")
BORDER_CELL = Border(left=THIN_GRAY, right=THIN_GRAY, top=THIN_GRAY, bottom=THIN_GRAY)

# --- Alignments ----------------------------------------------------------

ALIGN_RIGHT = Alignment(horizontal="right", vertical="center")
ALIGN_LEFT = Alignment(horizontal="left", vertical="center")
ALIGN_CENTER = Alignment(horizontal="center", vertical="center")
```

- [ ] **Step 2: Smoke-import to catch typos**

Run: `uv run python -c "from peerbench.export import style; print(style.FILL_ANCHOR.fgColor.rgb)"`
Expected: prints `00E8EEF7` or similar (openpyxl prepends the alpha channel).

- [ ] **Step 3: Type-check**

Run: `uv run pyright src/peerbench/export/style.py`
Expected: 0 errors.

- [ ] **Step 4: Commit**

```bash
git add src/peerbench/export/style.py
git commit -m "feat(export): openpyxl style constants"
```

---

## Task 6: Add ELNATR to INCOME_FIELDS

**Files:**
- Modify: `src/peerbench/fdic_fields.py`

`ELNATR` (Provision for credit losses) is required for the Comp Sheet I/S section. The pipeline doesn't track it today. Daily cron picks it up on next run; for dev we backfill via `peerbench ingest`.

- [ ] **Step 1: Edit the INCOME_FIELDS tuple**

Open `src/peerbench/fdic_fields.py`, find the `INCOME_FIELDS` tuple (around line 50–65), and append `ELNATR`:

```python
# Income statement
INCOME_FIELDS: tuple[str, ...] = (
    "NETINC",
    "NIM",
    "INTINC",
    "EINTEXP",
    "ERNAST",
    "ERNAST5",
    "NONII",
    "NONIX",
    "NTLNLS",
    "EAMINTAN",
    "ELNATR",  # Provision for credit losses — Phase 4.2 Comp Sheet I/S.
)
```

- [ ] **Step 2: Verify nothing else broke**

Run: `uv run pytest tests/unit tests/contract -x`
Expected: PASS (no regressions in registry / ratio handler tests).

- [ ] **Step 3: Backfill the 5-bank slice for the 8 most-recent quarters (manual, dev-time)**

```bash
for cert in 4063 4214 110 11063 5510; do
  uv run peerbench ingest --cert "$cert" --quarters 8
done
```

Each run upserts `ELNATR` into `facts` for that cert × quarter (and re-upserts all other fields idempotently). No-op if `ELNATR` already exists — the next daily cron would have done this anyway.

- [ ] **Step 4: Commit**

```bash
git add src/peerbench/fdic_fields.py
git commit -m "feat(pipeline): track ELNATR (provision for credit losses)"
```

---

## Task 7: data/cover.py — build_cover

**Files:**
- Create: `src/peerbench/export/data/cover.py`
- Create: `tests/unit/test_export_cover.py`

- [ ] **Step 1: Write the failing test**

```python
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from peerbench.export.data.cover import build_cover


def test_build_cover_populates_required_fields() -> None:
    cover = build_cover(
        anchor_cert=4063,
        anchor_name="MidFirst Bank",
        quarter_id="2025-Q4",
        quarter_end_date=datetime(2025, 12, 31, tzinfo=UTC).date(),
        generated_at=datetime(2026, 5, 23, 12, 0, 0, tzinfo=UTC),
        data_vintage=datetime(2026, 5, 22, 6, 11, 42, tzinfo=UTC),
    )
    assert cover.anchor_cert == 4063
    assert cover.anchor_name == "MidFirst Bank"
    assert cover.quarter_id == "2025-Q4"
    assert cover.quarter_end == "December 31, 2025"
    assert cover.data_vintage == "2026-05-22"


def test_build_cover_no_extra_notes_by_default() -> None:
    cover = build_cover(
        anchor_cert=4063,
        anchor_name="MidFirst",
        quarter_id="2025-Q4",
        quarter_end_date=datetime(2025, 12, 31, tzinfo=UTC).date(),
        generated_at=datetime(2026, 5, 23, tzinfo=UTC),
        data_vintage=datetime(2026, 5, 22, tzinfo=UTC),
    )
    assert cover.notes == []


def test_build_cover_anchor_warning_note_when_no_ratios() -> None:
    cover = build_cover(
        anchor_cert=4063,
        anchor_name="MidFirst",
        quarter_id="2025-Q4",
        quarter_end_date=datetime(2025, 12, 31, tzinfo=UTC).date(),
        generated_at=datetime(2026, 5, 23, tzinfo=UTC),
        data_vintage=datetime(2026, 5, 22, tzinfo=UTC),
        anchor_has_no_ratios=True,
    )
    assert "Anchor has no ratios for 2025-Q4" in cover.notes[0]


def test_build_cover_no_peers_warning_note() -> None:
    cover = build_cover(
        anchor_cert=4063,
        anchor_name="MidFirst",
        quarter_id="2025-Q4",
        quarter_end_date=datetime(2025, 12, 31, tzinfo=UTC).date(),
        generated_at=datetime(2026, 5, 23, tzinfo=UTC),
        data_vintage=datetime(2026, 5, 22, tzinfo=UTC),
        active_peer_count=0,
    )
    assert any("no active peers" in n.lower() for n in cover.notes)
```

- [ ] **Step 2: Run, watch fail**

Run: `uv run pytest tests/unit/test_export_cover.py -v`
Expected: FAIL with ModuleNotFoundError.

- [ ] **Step 3: Implementation**

```python
from __future__ import annotations

from datetime import date, datetime

from peerbench.export.data.types import CoverTab


def build_cover(
    *,
    anchor_cert: int,
    anchor_name: str,
    quarter_id: str,
    quarter_end_date: date,
    generated_at: datetime,
    data_vintage: datetime,
    anchor_has_no_ratios: bool = False,
    active_peer_count: int | None = None,
) -> CoverTab:
    """Compose the Cover tab payload.

    `data_vintage` is the max `quarters.ingest_at` across data in the
    workbook; rendered as a date (no time) for analyst readability.
    """
    notes: list[str] = []
    if anchor_has_no_ratios:
        notes.append(f"Anchor has no ratios for {quarter_id}.")
    if active_peer_count is not None and active_peer_count == 0:
        notes.append(
            "No active peers in the institutions table — workbook contains "
            "anchor data only.",
        )
    return CoverTab(
        anchor_cert=anchor_cert,
        anchor_name=anchor_name,
        quarter_id=quarter_id,
        quarter_end=quarter_end_date.strftime("%B %-d, %Y"),
        generated_at=generated_at,
        data_vintage=data_vintage.strftime("%Y-%m-%d"),
        notes=notes,
    )
```

- [ ] **Step 4: Run, watch pass**

Run: `uv run pytest tests/unit/test_export_cover.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add src/peerbench/export/data/cover.py tests/unit/test_export_cover.py
git commit -m "feat(export): build_cover with optional anchor/peer warning notes"
```

---

## Task 8: data/methodology.py — build_methodology + contract test

**Files:**
- Create: `src/peerbench/export/data/methodology.py`
- Create: `tests/unit/test_export_methodology.py`
- Create: `tests/contract/test_export_methodology_completeness.py`

`build_methodology` reads `ratio_defs` rows and emits one block per ratio. The contract test asserts every ratio in `data/ratios.csv` (the canonical CSV source-of-truth — `ratio_defs` table mirrors it post-seed) yields a block.

- [ ] **Step 1: Write the failing unit test**

```python
from __future__ import annotations

from peerbench.db import RatioDef
from peerbench.export.data.methodology import (
    build_methodology,
    render_regulatory_threshold,
)


def test_render_regulatory_threshold_amber_red() -> None:
    payload = {"amber_pct": 300, "red_pct": 400, "citation": "SR 07-1 §III.A"}
    rendered = render_regulatory_threshold(payload)
    assert "300" in rendered
    assert "400" in rendered
    assert "SR 07-1 §III.A" in rendered


def test_render_regulatory_threshold_none() -> None:
    assert render_regulatory_threshold(None) is None


def test_render_regulatory_threshold_amber_only() -> None:
    rendered = render_regulatory_threshold(
        {"amber_pct": 100, "citation": "OCC Bulletin 2006-46"}
    )
    assert rendered is not None
    assert "100" in rendered
    assert "OCC Bulletin 2006-46" in rendered


def test_build_methodology_emits_block_per_ratio_def() -> None:
    defs = [
        RatioDef(
            ratio_id="nim",
            display_name="Net Interest Margin",
            category="profitability",
            numerator_formula="Net interest income",
            denominator_formula="Average earning assets",
            annualize=True,
            avg_or_eop="AVG",
            fdic_precomputed_code="NIMY",
            ubpr_concept="UBPR3404",
            regulatory_threshold=None,
            suppress_when=None,
            notes="Non-tax-equivalent.",
        ),
        RatioDef(
            ratio_id="cre_rbc",
            display_name="CRE / Total RBC",
            category="concentration",
            numerator_formula="CRE loans",
            denominator_formula="Total RBC",
            annualize=False,
            avg_or_eop="EOP",
            fdic_precomputed_code=None,
            ubpr_concept=None,
            regulatory_threshold={
                "amber_pct": 300,
                "red_pct": 400,
                "citation": "SR 07-1 §III.A",
            },
            suppress_when=None,
            notes=None,
        ),
    ]
    field_deps = {
        "nim": ["INTINC", "EINTEXP", "ERNAST5"],
        "cre_rbc": ["LNRECONS", "LNREMULT", "LNRENRES", "RBCT1J", "RBCT2"],
    }
    tab = build_methodology(defs, field_deps=field_deps)
    assert len(tab.blocks) == 2
    nim_block = tab.blocks[0]
    assert nim_block.ratio_id == "nim"
    assert "Net interest income" in nim_block.formula
    assert nim_block.annualization == "YTD × 4/Qn"
    assert nim_block.basis == "AVG"
    assert nim_block.fdic_precomputed == "NIMY"
    assert nim_block.regulatory_threshold is None
    assert "INTINC" in nim_block.source_fields
    cre_block = tab.blocks[1]
    assert cre_block.regulatory_threshold is not None
    assert "300" in cre_block.regulatory_threshold


def test_build_methodology_intro_notes_present() -> None:
    tab = build_methodology([], field_deps={})
    assert len(tab.intro_notes) >= 5  # data sources, annualization, TE, CBLR, restatement, citations
```

- [ ] **Step 2: Write the contract test**

`tests/contract/test_export_methodology_completeness.py`:

```python
"""Contract: every ratio in data/ratios.csv (the CSV source of truth)
gets a methodology block. Catches a missing field-deps entry or a
silently dropped row."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from peerbench.export.data.methodology import build_methodology
from peerbench.ratio_defs_io import load_ratio_defs

REPO_ROOT = Path(__file__).resolve().parents[2]
FIELD_DEPS_PATH = REPO_ROOT / "web" / "lib" / "ratio-field-deps.generated.json"


@pytest.mark.contract
def test_methodology_covers_every_ratio() -> None:
    csv_rows = load_ratio_defs()
    field_deps = json.loads(FIELD_DEPS_PATH.read_text(encoding="utf-8"))

    # Build a RatioDef-like adapter — load_ratio_defs returns ParsedRatioDef
    # dataclasses (not ORM rows). build_methodology only reads attributes,
    # so a duck-typed list works.
    defs = list(csv_rows)
    tab = build_methodology(defs, field_deps=field_deps)
    csv_ids = {r.ratio_id for r in csv_rows}
    block_ids = {b.ratio_id for b in tab.blocks}
    assert csv_ids == block_ids
```

- [ ] **Step 3: Watch tests fail**

Run: `uv run pytest tests/unit/test_export_methodology.py tests/contract/test_export_methodology_completeness.py -v`
Expected: FAIL with ModuleNotFoundError.

- [ ] **Step 4: Write the implementation**

```python
from __future__ import annotations

from typing import Any, Protocol

from peerbench.export.data.types import (
    MethodologyBlock,
    MethodologyNote,
    MethodologyTab,
)


class RatioDefLike(Protocol):
    ratio_id: str
    display_name: str
    category: str
    numerator_formula: str
    denominator_formula: str
    annualize: bool
    avg_or_eop: str
    fdic_precomputed_code: str | None
    regulatory_threshold: dict[str, Any] | None
    notes: str | None


INTRO_NOTES: list[MethodologyNote] = [
    MethodologyNote(
        label="Data sources",
        text="FDIC BankFind API + FFIEC CDR bulk files.",
    ),
    MethodologyNote(
        label="Annualization",
        text="YTD income × 4/Qn for Q1–Q3; Q4 not annualized.",
    ),
    MethodologyNote(
        label="Tax-equivalent",
        text=(
            "Ratios reported on a non-TE basis. UBPR uses TE; expect 5–15 "
            "bps gap on NIM/yields depending on muni mix."
        ),
    ),
    MethodologyNote(
        label="Average vs period-end",
        text=(
            "Per ratio_defs.avg_or_eop. AVG ratios use FDIC 5-period YTD "
            "averages."
        ),
    ),
    MethodologyNote(
        label="CBLR filers",
        text=(
            "Small banks under the Community Bank Leverage Ratio framework "
            "do not report Tier 1 RBC / Total RBC / CET1. Those cells "
            "render em-dash and are excluded from quartile cutoffs."
        ),
    ),
    MethodologyNote(
        label="Restatement detector",
        text=(
            "Incoming FDIC values are compared to stored values; on diff, "
            "the fact is flagged restated, logged, and affected ratios are "
            "recomputed. Forward-quarter ratios that depend on 5-period "
            "averages are also flagged partial."
        ),
    ),
    MethodologyNote(
        label="Regulatory citations",
        text="SR 07-1, OCC Bulletin 2006-46, FIL-23-2023.",
    ),
]


def render_regulatory_threshold(payload: dict[str, Any] | None) -> str | None:
    if payload is None:
        return None
    amber = payload.get("amber_pct")
    red = payload.get("red_pct")
    citation = payload.get("citation", "")
    parts: list[str] = []
    if amber is not None:
        parts.append(f"Amber ≥ {amber}%")
    if red is not None:
        parts.append(f"Red ≥ {red}%")
    body = ", ".join(parts) if parts else "see citation"
    if citation:
        return f"{body} — {citation}"
    return body


def build_methodology(
    ratio_defs: list[RatioDefLike],
    *,
    field_deps: dict[str, list[str]],
) -> MethodologyTab:
    blocks: list[MethodologyBlock] = []
    for r in ratio_defs:
        blocks.append(
            MethodologyBlock(
                ratio_id=r.ratio_id,
                display_name=r.display_name,
                category=r.category,
                formula=f"{r.numerator_formula} / {r.denominator_formula}",
                source_fields=list(field_deps.get(r.ratio_id, [])),
                annualization=(
                    "YTD × 4/Qn" if r.annualize else "Not annualized"
                ),
                basis=r.avg_or_eop,
                fdic_precomputed=r.fdic_precomputed_code,
                regulatory_threshold=render_regulatory_threshold(
                    r.regulatory_threshold
                ),
                notes=r.notes,
            )
        )
    return MethodologyTab(intro_notes=INTRO_NOTES, blocks=blocks)
```

- [ ] **Step 5: Run, watch pass**

Run: `uv run pytest tests/unit/test_export_methodology.py tests/contract/test_export_methodology_completeness.py -v`
Expected: PASS (6 tests).

- [ ] **Step 6: Commit**

```bash
git add src/peerbench/export/data/methodology.py tests/unit/test_export_methodology.py tests/contract/test_export_methodology_completeness.py
git commit -m "feat(export): build_methodology + completeness contract test"
```

---

## Task 9: data/restatement.py — build_restatement_log

**Files:**
- Create: `src/peerbench/export/data/restatement.py`
- Create: `tests/unit/test_export_restatement.py`

- [ ] **Step 1: Write the failing test**

```python
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from peerbench.export.data.restatement import (
    build_restatement_log,
    derive_affected_ratios,
)


def test_derive_affected_ratios_simple_case() -> None:
    field_deps = {
        "nim": ["INTINC", "EINTEXP", "ERNAST5"],
        "roa": ["NETINC", "ASSET5"],
        "eff_ratio": ["NONIX", "EAMINTAN", "NIM", "NONII"],
    }
    affected = derive_affected_ratios("NIM", field_deps)
    # NIM appears in both nim (as field) and eff_ratio (NIM as a field code).
    # Note: field_code "NIM" is both a ratio_id ('nim') and a fact code (NIM = net int income).
    assert "nim" in affected
    assert "eff_ratio" in affected


def test_derive_affected_ratios_no_match() -> None:
    assert derive_affected_ratios("CBLRIND", {"nim": ["INTINC"]}) == []


def test_build_restatement_log_filters_to_workbook_window() -> None:
    # Restatement of a 2023-Q4 fact (outside the 8-quarter window) is dropped.
    events = [
        _make_event(
            quarter_id="2025-Q3",
            field_code="NETINC",
            cert=4063,
            old=Decimal("100"),
            new=Decimal("120"),
        ),
        _make_event(
            quarter_id="2023-Q4",  # outside window
            field_code="NETINC",
            cert=4063,
            old=Decimal("100"),
            new=Decimal("120"),
        ),
    ]
    bank_names = {4063: "MidFirst"}
    field_deps = {"roa": ["NETINC", "ASSET5"]}
    window = {"2024-Q1", "2024-Q2", "2024-Q3", "2024-Q4",
              "2025-Q1", "2025-Q2", "2025-Q3", "2025-Q4"}
    tab = build_restatement_log(
        events, bank_names=bank_names, field_deps=field_deps, window=window
    )
    assert len(tab.rows) == 1
    assert tab.rows[0].quarter_id == "2025-Q3"
    assert "roa" in tab.rows[0].affected_ratios


def test_build_restatement_log_filters_to_workbook_ratios() -> None:
    # A field code that no workbook ratio reads is dropped.
    events = [
        _make_event(
            quarter_id="2025-Q4",
            field_code="UNKNOWN_FIELD",
            cert=4063,
            old=Decimal("100"),
            new=Decimal("120"),
        ),
    ]
    tab = build_restatement_log(
        events,
        bank_names={4063: "MidFirst"},
        field_deps={"nim": ["INTINC"]},
        window={"2025-Q4"},
    )
    assert tab.rows == []


def test_build_restatement_log_sorts_detected_at_desc() -> None:
    events = [
        _make_event(
            quarter_id="2025-Q4",
            field_code="NETINC",
            cert=4063,
            old=Decimal("100"),
            new=Decimal("110"),
            detected_at=datetime(2026, 1, 1, tzinfo=UTC),
        ),
        _make_event(
            quarter_id="2025-Q4",
            field_code="NETINC",
            cert=4063,
            old=Decimal("110"),
            new=Decimal("120"),
            detected_at=datetime(2026, 5, 1, tzinfo=UTC),
        ),
    ]
    tab = build_restatement_log(
        events,
        bank_names={4063: "MidFirst"},
        field_deps={"roa": ["NETINC"]},
        window={"2025-Q4"},
    )
    assert tab.rows[0].detected_at > tab.rows[1].detected_at


def _make_event(
    *,
    cert: int,
    quarter_id: str,
    field_code: str,
    old: Decimal | None,
    new: Decimal | None,
    detected_at: datetime | None = None,
) -> dict[str, object]:
    return {
        "detected_at": detected_at or datetime(2026, 5, 22, 12, 0, 0, tzinfo=UTC),
        "cert": cert,
        "quarter_id": quarter_id,
        "field_code": field_code,
        "old_value": old,
        "new_value": new,
    }
```

- [ ] **Step 2: Watch fail**

Run: `uv run pytest tests/unit/test_export_restatement.py -v`
Expected: FAIL with ModuleNotFoundError.

- [ ] **Step 3: Implementation**

```python
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from peerbench.export.data.types import RestatementRow, RestatementTab


def derive_affected_ratios(
    field_code: str,
    field_deps: dict[str, list[str]],
) -> list[str]:
    """Return ratio_ids whose handler reads the given field, in input order."""
    return [rid for rid, fields in field_deps.items() if field_code in fields]


def build_restatement_log(
    events: list[dict[str, Any]],
    *,
    bank_names: dict[int, str],
    field_deps: dict[str, list[str]],
    window: set[str],
) -> RestatementTab:
    """Filter quality_log restatement events down to the workbook's relevant set.

    `events` is the list of rows from `quality_log` where event_type='restated'.
    Each row is a dict with keys: detected_at, cert, quarter_id, field_code,
    old_value, new_value. We filter to events whose quarter falls in `window`
    AND whose field_code is read by at least one workbook ratio, then we sort
    detected_at DESC and decorate with the affected-ratio list.
    """
    rows: list[RestatementRow] = []
    for ev in events:
        quarter_id = str(ev["quarter_id"])
        if quarter_id not in window:
            continue
        field_code = str(ev["field_code"])
        affected = derive_affected_ratios(field_code, field_deps)
        if not affected:
            continue
        cert = int(ev["cert"])
        rows.append(
            RestatementRow(
                detected_at=ev["detected_at"],
                cert=cert,
                bank_name=bank_names.get(cert, f"Cert {cert}"),
                quarter_id=quarter_id,
                field_code=field_code,
                old_value=ev.get("old_value"),
                new_value=ev.get("new_value"),
                affected_ratios=affected,
            )
        )
    rows.sort(key=lambda r: (r.detected_at, r.quarter_id), reverse=True)
    return RestatementTab(rows=rows)
```

- [ ] **Step 4: Run, watch pass**

Run: `uv run pytest tests/unit/test_export_restatement.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add src/peerbench/export/data/restatement.py tests/unit/test_export_restatement.py
git commit -m "feat(export): build_restatement_log + affected-ratios derivation"
```

---

## Task 10: data/summary.py — build_summary

**Files:**
- Create: `src/peerbench/export/data/summary.py`
- Create: `tests/unit/test_export_summary.py`

- [ ] **Step 1: Write the failing test**

```python
from __future__ import annotations

from decimal import Decimal

from peerbench.export.data.summary import (
    build_summary,
    compute_anchor_rank,
)


def test_compute_anchor_rank_higher_is_positive() -> None:
    # Anchor 50, peers 10/20/30/40 → anchor highest → rank 1.
    rank = compute_anchor_rank(
        anchor_value=Decimal(50),
        peer_values=[Decimal(10), Decimal(20), Decimal(30), Decimal(40)],
        direction="higher_is_positive",
    )
    assert rank == 1


def test_compute_anchor_rank_higher_is_negative_inverts() -> None:
    # Anchor 50, peers 10/20/30/40 → highest = worst for eff_ratio → rank 5.
    rank = compute_anchor_rank(
        anchor_value=Decimal(50),
        peer_values=[Decimal(10), Decimal(20), Decimal(30), Decimal(40)],
        direction="higher_is_negative",
    )
    assert rank == 5


def test_compute_anchor_rank_neutral_returns_none() -> None:
    rank = compute_anchor_rank(
        anchor_value=Decimal(50),
        peer_values=[Decimal(10), Decimal(20), Decimal(30), Decimal(40)],
        direction="neutral",
    )
    assert rank is None


def test_compute_anchor_rank_anchor_none_returns_none() -> None:
    rank = compute_anchor_rank(
        anchor_value=None,
        peer_values=[Decimal(10), Decimal(20)],
        direction="higher_is_positive",
    )
    assert rank is None


def test_compute_anchor_rank_drops_none_peers() -> None:
    # Suppressed peers (None) excluded from rank; rank is among non-None set.
    rank = compute_anchor_rank(
        anchor_value=Decimal(35),
        peer_values=[Decimal(10), None, Decimal(20), Decimal(40)],
        direction="higher_is_positive",
    )
    # Anchor 35 in {10, 20, 35, 40} → 2nd from top → rank 2.
    assert rank == 2


def test_build_summary_rows_anchor_first_in_columns() -> None:
    anchor = (4063, "MidFirst")
    peers = [(110, "BOK"), (4214, "Comerica")]
    ratio_defs = [_def("nim", "profitability", "Net Interest Margin")]
    ratios_by_cert = {
        4063: {"nim": Decimal("0.035")},
        110: {"nim": Decimal("0.030")},
        4214: {"nim": Decimal("0.028")},
    }
    suppressed = set()
    tab = build_summary(
        anchor=anchor,
        peers=peers,
        ratio_defs=ratio_defs,
        ratios_by_cert=ratios_by_cert,
        suppressed=suppressed,
    )
    assert tab.institution_columns[0] == anchor
    assert tab.institution_columns[1:] == peers
    assert tab.rows[0].anchor_value == Decimal("0.035")
    assert tab.rows[0].peer_values[110] == Decimal("0.030")


def test_build_summary_excludes_suppressed_from_median() -> None:
    anchor = (4063, "MidFirst")
    peers = [(110, "BOK"), (4214, "Comerica"), (5510, "Frost")]
    ratio_defs = [_def("tier1_rbc", "capital", "Tier 1 RBC")]
    ratios_by_cert = {
        4063: {"tier1_rbc": Decimal("0.11")},
        110: {"tier1_rbc": Decimal("0.12")},
        4214: {"tier1_rbc": None},  # CBLR filer
        5510: {"tier1_rbc": Decimal("0.13")},
    }
    # 4214 is suppressed for tier1_rbc (CBLR).
    suppressed = {(4214, "tier1_rbc")}
    tab = build_summary(
        anchor=anchor,
        peers=peers,
        ratio_defs=ratio_defs,
        ratios_by_cert=ratios_by_cert,
        suppressed=suppressed,
    )
    # Median of [0.12, 0.13] (4214 excluded) = 0.125.
    assert tab.rows[0].peer_median == Decimal("0.125")


def test_build_summary_neutral_direction_skips_rank() -> None:
    anchor = (4063, "MidFirst")
    peers = [(110, "BOK"), (4214, "Comerica"), (5510, "Frost"), (11063, "BankX")]
    ratio_defs = [_def("loans_assets", "balance_sheet", "Loans / Assets")]
    ratios_by_cert = {
        4063: {"loans_assets": Decimal("0.6")},
        110: {"loans_assets": Decimal("0.5")},
        4214: {"loans_assets": Decimal("0.7")},
        5510: {"loans_assets": Decimal("0.55")},
        11063: {"loans_assets": Decimal("0.65")},
    }
    tab = build_summary(
        anchor=anchor, peers=peers, ratio_defs=ratio_defs,
        ratios_by_cert=ratios_by_cert, suppressed=set()
    )
    assert tab.rows[0].anchor_rank is None  # neutral direction


def _def(rid: str, category: str, name: str, amber=None, red=None):
    # Minimal RatioDef-like for tests.
    from dataclasses import dataclass
    @dataclass
    class D:
        ratio_id: str
        display_name: str
        category: str
        regulatory_threshold: dict | None
    threshold = None
    if amber or red:
        threshold = {"amber_pct": amber, "red_pct": red}
    return D(rid, name, category, threshold)
```

- [ ] **Step 2: Watch fail**

Run: `uv run pytest tests/unit/test_export_summary.py -v`
Expected: FAIL with ModuleNotFoundError.

- [ ] **Step 3: Implementation**

```python
from __future__ import annotations

from decimal import Decimal
from typing import Any, Protocol

from peerbench.export.directions import direction_for
from peerbench.export.data.types import SummaryRow, SummaryTab


class RatioDefLike(Protocol):
    ratio_id: str
    display_name: str
    category: str
    regulatory_threshold: dict[str, Any] | None


def compute_anchor_rank(
    *,
    anchor_value: Decimal | None,
    peer_values: list[Decimal | None],
    direction: str,
) -> int | None:
    """Direction-aware rank, 1 = best.

    For higher_is_positive: rank 1 = highest value.
    For higher_is_negative: rank 1 = lowest value.
    For neutral: returns None (rank is misleading when there's no "better").
    """
    if direction == "neutral" or anchor_value is None:
        return None
    all_values = [v for v in [anchor_value, *peer_values] if v is not None]
    if direction == "higher_is_positive":
        sorted_values = sorted(all_values, reverse=True)
    else:
        sorted_values = sorted(all_values)
    return sorted_values.index(anchor_value) + 1


def _median(values: list[Decimal]) -> Decimal | None:
    if not values:
        return None
    sorted_values = sorted(values)
    n = len(sorted_values)
    mid = n // 2
    if n % 2 == 1:
        return sorted_values[mid]
    return (sorted_values[mid - 1] + sorted_values[mid]) / 2


def build_summary(
    *,
    anchor: tuple[int, str],
    peers: list[tuple[int, str]],
    ratio_defs: list[RatioDefLike],
    ratios_by_cert: dict[int, dict[str, Decimal | None]],
    suppressed: set[tuple[int, str]],
) -> SummaryTab:
    """Assemble the Summary tab payload.

    `ratios_by_cert[cert][ratio_id]` is the stored ratio value (fraction) or
    None. `suppressed` flags (cert, ratio_id) pairs whose data_quality is
    'suppressed' — those values are excluded from peer median + quartile
    cutoffs (mirrors dashboard).
    """
    rows: list[SummaryRow] = []
    anchor_cert = anchor[0]
    for r in ratio_defs:
        direction = direction_for(r.ratio_id)
        anchor_value = ratios_by_cert.get(anchor_cert, {}).get(r.ratio_id)

        peer_values_full: dict[int, Decimal | None] = {}
        peer_values_for_stats: list[Decimal] = []
        for cert, _name in peers:
            v = ratios_by_cert.get(cert, {}).get(r.ratio_id)
            if (cert, r.ratio_id) in suppressed:
                peer_values_full[cert] = None
            else:
                peer_values_full[cert] = v
                if v is not None:
                    peer_values_for_stats.append(v)

        peer_median = _median(peer_values_for_stats)
        peer_list_for_rank: list[Decimal | None] = [
            peer_values_full[c] for c, _ in peers
        ]
        rank = compute_anchor_rank(
            anchor_value=anchor_value,
            peer_values=peer_list_for_rank,
            direction=direction,
        )
        delta = (
            anchor_value - peer_median
            if anchor_value is not None and peer_median is not None
            else None
        )

        threshold = r.regulatory_threshold or {}
        amber_pct_raw = threshold.get("amber_pct")
        red_pct_raw = threshold.get("red_pct")

        rows.append(
            SummaryRow(
                ratio_id=r.ratio_id,
                display_name=r.display_name,
                category=r.category,
                anchor_value=anchor_value,
                peer_values=peer_values_full,
                peer_median=peer_median,
                anchor_rank=rank,
                delta_vs_median=delta,
                direction=direction,
                amber_pct=Decimal(amber_pct_raw) / 100 if amber_pct_raw else None,
                red_pct=Decimal(red_pct_raw) / 100 if red_pct_raw else None,
            )
        )
    return SummaryTab(institution_columns=[anchor, *peers], rows=rows)
```

- [ ] **Step 4: Run, watch pass**

Run: `uv run pytest tests/unit/test_export_summary.py -v`
Expected: PASS (8 tests).

- [ ] **Step 5: Commit**

```bash
git add src/peerbench/export/data/summary.py tests/unit/test_export_summary.py
git commit -m "feat(export): build_summary with direction-aware rank + median"
```

---

## Task 11: data/comp_sheet.py — build_comp_sheets

**Files:**
- Create: `src/peerbench/export/data/comp_sheet.py`
- Create: `tests/unit/test_export_comp_sheet.py`

- [ ] **Step 1: Write the failing test**

```python
from __future__ import annotations

from decimal import Decimal

from peerbench.export.data.comp_sheet import (
    INCOME_STATEMENT_LINES,
    BALANCE_SHEET_LINES,
    build_comp_sheets,
    sanitize_sheet_name,
)


def test_sanitize_sheet_name_strips_invalid_chars() -> None:
    assert sanitize_sheet_name("Foo/Bar*Baz[1]") == "FooBarBaz1"


def test_sanitize_sheet_name_truncates_to_31_chars() -> None:
    name = "A" * 50
    assert len(sanitize_sheet_name(name)) == 31


def test_sanitize_sheet_name_collision_appends_suffix() -> None:
    # If we sanitize two names to the same result, the second gets a numeric
    # suffix. Caller passes a set of used names.
    used: set[str] = set()
    a = sanitize_sheet_name("BOK Financial Corp Inc.", used=used)
    used.add(a)
    b = sanitize_sheet_name("BOK Financial Corp Inc.", used=used)
    used.add(b)
    assert a != b
    assert b.startswith(a[:29])  # suffix appended


def test_income_statement_lines_in_locked_order() -> None:
    labels = [line.label for line in INCOME_STATEMENT_LINES]
    codes = [line.field_code for line in INCOME_STATEMENT_LINES]
    assert labels == [
        "Interest income",
        "Interest expense",
        "Net interest income",
        "Provision for credit losses",
        "Non-interest income",
        "Non-interest expense",
        "Net income",
    ]
    assert codes == [
        "INTINC", "EINTEXP", "NIM", "ELNATR", "NONII", "NONIX", "NETINC",
    ]


def test_balance_sheet_lines_in_locked_order() -> None:
    labels = [line.label for line in BALANCE_SHEET_LINES]
    codes = [line.field_code for line in BALANCE_SHEET_LINES]
    assert labels == [
        "Total assets",
        "Loans (gross)",
        "Securities",
        "Cash & equivalents",
        "Total deposits",
        "Total liabilities",
        "Total equity",
    ]
    assert codes == ["ASSET", "LNLSGR", "SC", "CHBAL", "DEP", "LIAB", "EQ"]


def test_build_comp_sheets_one_per_peer_skips_anchor() -> None:
    anchor = (4063, "MidFirst")
    peers = [(110, "BOK"), (4214, "Comerica")]
    facts = _empty_facts()
    ratios = {
        4063: {"nim": Decimal("0.035")},
        110: {"nim": Decimal("0.030")},
        4214: {"nim": Decimal("0.028")},
    }
    ratio_defs = [_def("nim", "profitability", "Net Interest Margin",
                       "Net interest income", "Average earning assets")]
    sheets = build_comp_sheets(
        anchor=anchor,
        peers=peers,
        quarter_id="2025-Q4",
        income_statement_quarter_ids=["2025-Q1", "2025-Q2", "2025-Q3", "2025-Q4"],
        facts_by_cert_quarter=facts,
        ratios_by_cert=ratios,
        ratio_defs=ratio_defs,
    )
    assert len(sheets) == 2  # one per peer
    bok_sheet = next(s for s in sheets if s.peer_cert == 110)
    assert bok_sheet.anchor_cert == 4063
    assert bok_sheet.ratios[0].anchor_value == Decimal("0.035")
    assert bok_sheet.ratios[0].peer_value == Decimal("0.030")


def test_build_comp_sheets_picks_correct_field_values() -> None:
    # ASSET fact for anchor in 2025-Q4 should land in the B/S anchor column.
    anchor = (4063, "MidFirst")
    peers = [(110, "BOK")]
    facts = {
        (4063, "2025-Q4"): {"ASSET": Decimal("41200000")},
        (110, "2025-Q4"): {"ASSET": Decimal("48000000")},
    }
    sheets = build_comp_sheets(
        anchor=anchor, peers=peers, quarter_id="2025-Q4",
        income_statement_quarter_ids=["2025-Q4"],
        facts_by_cert_quarter=facts, ratios_by_cert={}, ratio_defs=[],
    )
    bs = sheets[0].balance_sheet
    asset_line = next(line for line in bs if line.field_code == "ASSET")
    assert asset_line.anchor_value == Decimal("41200000")
    assert asset_line.peer_value == Decimal("48000000")


def _empty_facts() -> dict[tuple[int, str], dict[str, Decimal | None]]:
    return {}


def _def(rid: str, category: str, name: str, num: str, den: str):
    from dataclasses import dataclass
    @dataclass
    class D:
        ratio_id: str
        display_name: str
        category: str
        numerator_formula: str
        denominator_formula: str
    return D(rid, name, category, num, den)
```

- [ ] **Step 2: Watch fail**

Run: `uv run pytest tests/unit/test_export_comp_sheet.py -v`
Expected: FAIL with ModuleNotFoundError.

- [ ] **Step 3: Implementation**

```python
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from peerbench.export.directions import direction_for
from peerbench.export.data.types import (
    BalanceSheetLine,
    CompRatioRow,
    CompSheetTab,
    IncomeStatementLine,
)


@dataclass(frozen=True)
class _LineSpec:
    label: str
    field_code: str


INCOME_STATEMENT_LINES: tuple[_LineSpec, ...] = (
    _LineSpec("Interest income", "INTINC"),
    _LineSpec("Interest expense", "EINTEXP"),
    _LineSpec("Net interest income", "NIM"),
    _LineSpec("Provision for credit losses", "ELNATR"),
    _LineSpec("Non-interest income", "NONII"),
    _LineSpec("Non-interest expense", "NONIX"),
    _LineSpec("Net income", "NETINC"),
)

BALANCE_SHEET_LINES: tuple[_LineSpec, ...] = (
    _LineSpec("Total assets", "ASSET"),
    _LineSpec("Loans (gross)", "LNLSGR"),
    _LineSpec("Securities", "SC"),
    _LineSpec("Cash & equivalents", "CHBAL"),
    _LineSpec("Total deposits", "DEP"),
    _LineSpec("Total liabilities", "LIAB"),
    _LineSpec("Total equity", "EQ"),
)

_INVALID_SHEET_CHARS = re.compile(r"[\[\]:*?/\\]")
_MAX_SHEET_NAME_LEN = 31


def sanitize_sheet_name(name: str, *, used: set[str] | None = None) -> str:
    """Sanitize and truncate to Excel's 31-char sheet-name limit.

    Strips invalid characters [ ] : * ? / \\.  If `used` is provided and
    the result collides, appends a numeric suffix (-2, -3, ...) and keeps
    the total length ≤ 31.
    """
    cleaned = _INVALID_SHEET_CHARS.sub("", name).strip()
    base = cleaned[:_MAX_SHEET_NAME_LEN]
    if used is None or base not in used:
        return base
    i = 2
    while True:
        suffix = f"-{i}"
        truncated = base[: _MAX_SHEET_NAME_LEN - len(suffix)]
        candidate = f"{truncated}{suffix}"
        if candidate not in used:
            return candidate
        i += 1


class RatioDefLike(Protocol):
    ratio_id: str
    display_name: str
    category: str
    numerator_formula: str
    denominator_formula: str


def build_comp_sheets(
    *,
    anchor: tuple[int, str],
    peers: list[tuple[int, str]],
    quarter_id: str,
    income_statement_quarter_ids: list[str],
    facts_by_cert_quarter: dict[tuple[int, str], dict[str, Decimal | None]],
    ratios_by_cert: dict[int, dict[str, Decimal | None]],
    ratio_defs: list[RatioDefLike],
) -> list[CompSheetTab]:
    """One CompSheetTab per peer (anchor excluded)."""
    used_sheet_names: set[str] = set()
    sheets: list[CompSheetTab] = []
    anchor_cert, anchor_name = anchor

    for peer_cert, peer_name in peers:
        sheet_name = sanitize_sheet_name(peer_name, used=used_sheet_names)
        used_sheet_names.add(sheet_name)

        income_lines: list[IncomeStatementLine] = []
        for spec in INCOME_STATEMENT_LINES:
            anchor_values = [
                facts_by_cert_quarter.get((anchor_cert, q), {}).get(spec.field_code)
                for q in income_statement_quarter_ids
            ]
            peer_values = [
                facts_by_cert_quarter.get((peer_cert, q), {}).get(spec.field_code)
                for q in income_statement_quarter_ids
            ]
            income_lines.append(
                IncomeStatementLine(
                    label=spec.label,
                    field_code=spec.field_code,
                    anchor_values=anchor_values,
                    peer_values=peer_values,
                )
            )

        balance_lines: list[BalanceSheetLine] = []
        anchor_facts = facts_by_cert_quarter.get((anchor_cert, quarter_id), {})
        peer_facts = facts_by_cert_quarter.get((peer_cert, quarter_id), {})
        for spec in BALANCE_SHEET_LINES:
            balance_lines.append(
                BalanceSheetLine(
                    label=spec.label,
                    field_code=spec.field_code,
                    anchor_value=anchor_facts.get(spec.field_code),
                    peer_value=peer_facts.get(spec.field_code),
                )
            )

        ratio_rows: list[CompRatioRow] = []
        anchor_ratios = ratios_by_cert.get(anchor_cert, {})
        peer_ratios = ratios_by_cert.get(peer_cert, {})
        for r in ratio_defs:
            ratio_rows.append(
                CompRatioRow(
                    ratio_id=r.ratio_id,
                    display_name=r.display_name,
                    category=r.category,
                    formula=f"{r.numerator_formula} / {r.denominator_formula}",
                    anchor_value=anchor_ratios.get(r.ratio_id),
                    peer_value=peer_ratios.get(r.ratio_id),
                    direction=direction_for(r.ratio_id),
                )
            )

        sheets.append(
            CompSheetTab(
                sheet_name=sheet_name,
                peer_cert=peer_cert,
                peer_name=peer_name,
                anchor_cert=anchor_cert,
                anchor_name=anchor_name,
                quarter_id=quarter_id,
                income_statement_quarters=income_statement_quarter_ids,
                income_statement=income_lines,
                balance_sheet=balance_lines,
                ratios=ratio_rows,
            )
        )
    return sheets
```

- [ ] **Step 4: Run, watch pass**

Run: `uv run pytest tests/unit/test_export_comp_sheet.py -v`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add src/peerbench/export/data/comp_sheet.py tests/unit/test_export_comp_sheet.py
git commit -m "feat(export): build_comp_sheets + sheet-name sanitization"
```

---

## Task 12: data/time_series.py — build_time_series

**Files:**
- Create: `src/peerbench/export/data/time_series.py`
- Create: `tests/unit/test_export_time_series.py`

- [ ] **Step 1: Write the failing test**

```python
from __future__ import annotations

from decimal import Decimal

from peerbench.export.data.time_series import build_time_series


def test_build_time_series_one_tab_per_category() -> None:
    ratio_defs = [
        _def("nim", "profitability", "Net Interest Margin",
             "Net interest income", "Avg earning assets"),
        _def("eff_ratio", "profitability", "Efficiency Ratio",
             "NIE - amort", "NII + Non-int inc"),
        _def("loans_assets", "balance_sheet", "Loans / Assets",
             "Loans", "Assets"),
    ]
    anchor = (4063, "MidFirst")
    peers = [(110, "BOK")]
    quarter_ids = ["2024-Q1", "2024-Q2", "2024-Q3", "2024-Q4",
                   "2025-Q1", "2025-Q2", "2025-Q3", "2025-Q4"]
    ratios = {
        4063: {(q, "nim"): Decimal("0.035") for q in quarter_ids},
        110: {(q, "nim"): Decimal("0.030") for q in quarter_ids},
    }
    tabs = build_time_series(
        anchor=anchor, peers=peers, quarter_ids=quarter_ids,
        ratios_by_cert_quarter=ratios, ratio_defs=ratio_defs,
    )
    # 2 categories present (profitability + balance_sheet) → 2 tabs.
    categories = [t.category for t in tabs]
    assert "profitability" in categories
    assert "balance_sheet" in categories


def test_build_time_series_anchor_pinned_first_in_each_block() -> None:
    ratio_defs = [_def("nim", "profitability", "NIM", "x", "y")]
    anchor = (4063, "MidFirst")
    peers = [(110, "BOK"), (4214, "Comerica")]
    quarter_ids = ["2025-Q4"]
    ratios = {
        4063: {("2025-Q4", "nim"): Decimal("0.035")},
        110: {("2025-Q4", "nim"): Decimal("0.030")},
        4214: {("2025-Q4", "nim"): Decimal("0.028")},
    }
    tabs = build_time_series(
        anchor=anchor, peers=peers, quarter_ids=quarter_ids,
        ratios_by_cert_quarter=ratios, ratio_defs=ratio_defs,
    )
    block = tabs[0].blocks[0]
    assert block.rows[0][0] == 4063  # anchor first
    assert block.rows[0][1] == "MidFirst"


def test_build_time_series_8_quarters_oldest_first() -> None:
    ratio_defs = [_def("nim", "profitability", "NIM", "x", "y")]
    quarter_ids = ["2024-Q1", "2024-Q2", "2024-Q3", "2024-Q4",
                   "2025-Q1", "2025-Q2", "2025-Q3", "2025-Q4"]
    tabs = build_time_series(
        anchor=(4063, "MidFirst"), peers=[],
        quarter_ids=quarter_ids,
        ratios_by_cert_quarter={4063: {}},
        ratio_defs=ratio_defs,
    )
    assert tabs[0].blocks[0].quarter_ids == quarter_ids


def test_build_time_series_missing_value_renders_none() -> None:
    ratio_defs = [_def("nim", "profitability", "NIM", "x", "y")]
    quarter_ids = ["2025-Q3", "2025-Q4"]
    ratios = {4063: {("2025-Q4", "nim"): Decimal("0.035")}}  # Q3 missing
    tabs = build_time_series(
        anchor=(4063, "MidFirst"), peers=[],
        quarter_ids=quarter_ids,
        ratios_by_cert_quarter=ratios, ratio_defs=ratio_defs,
    )
    values = tabs[0].blocks[0].rows[0][2]
    assert values[0] is None
    assert values[1] == Decimal("0.035")


def _def(rid: str, category: str, name: str, num: str, den: str):
    from dataclasses import dataclass
    @dataclass
    class D:
        ratio_id: str
        display_name: str
        category: str
        numerator_formula: str
        denominator_formula: str
    return D(rid, name, category, num, den)
```

- [ ] **Step 2: Watch fail**

Run: `uv run pytest tests/unit/test_export_time_series.py -v`
Expected: FAIL with ModuleNotFoundError.

- [ ] **Step 3: Implementation**

```python
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Protocol

from peerbench.export.directions import direction_for
from peerbench.export.data.comp_sheet import sanitize_sheet_name
from peerbench.export.data.types import (
    TimeSeriesBlock,
    TimeSeriesTab,
)

# Mirrors web/lib/ratio-order.ts CATEGORY_LABELS.
CATEGORY_LABELS = {
    "profitability": "Profitability",
    "yields": "Yields & costs",
    "balance_sheet": "Balance sheet mix",
    "asset_quality": "Asset quality",
    "capital": "Capital",
    "concentration": "Concentration",
    "liquidity": "Liquidity & deposit composition",
}

CATEGORY_ORDER = (
    "profitability", "yields", "balance_sheet", "asset_quality",
    "capital", "concentration", "liquidity",
)


class RatioDefLike(Protocol):
    ratio_id: str
    display_name: str
    category: str
    numerator_formula: str
    denominator_formula: str


def build_time_series(
    *,
    anchor: tuple[int, str],
    peers: list[tuple[int, str]],
    quarter_ids: list[str],
    ratios_by_cert_quarter: dict[int, dict[tuple[str, str], Decimal | None]],
    ratio_defs: list[RatioDefLike],
) -> list[TimeSeriesTab]:
    """One tab per category present in `ratio_defs`. Stacked blocks per ratio.

    `ratios_by_cert_quarter[cert][(quarter_id, ratio_id)]` is the stored value
    or None.
    """
    by_category: dict[str, list[RatioDefLike]] = defaultdict(list)
    for r in ratio_defs:
        by_category[r.category].append(r)

    institutions = [anchor, *peers]
    used_names: set[str] = set()
    tabs: list[TimeSeriesTab] = []
    for category in CATEGORY_ORDER:
        ratios_in_cat = by_category.get(category)
        if not ratios_in_cat:
            continue
        blocks: list[TimeSeriesBlock] = []
        for r in ratios_in_cat:
            rows: list[tuple[int, str, list[Decimal | None]]] = []
            for cert, name in institutions:
                vals = [
                    ratios_by_cert_quarter.get(cert, {}).get((q, r.ratio_id))
                    for q in quarter_ids
                ]
                rows.append((cert, name, vals))
            blocks.append(
                TimeSeriesBlock(
                    ratio_id=r.ratio_id,
                    display_name=r.display_name,
                    formula=f"{r.numerator_formula} / {r.denominator_formula}",
                    direction=direction_for(r.ratio_id),
                    quarter_ids=list(quarter_ids),
                    rows=rows,
                )
            )
        sheet_name = sanitize_sheet_name(
            CATEGORY_LABELS[category], used=used_names
        )
        used_names.add(sheet_name)
        tabs.append(
            TimeSeriesTab(
                sheet_name=sheet_name,
                category=category,
                category_label=CATEGORY_LABELS[category],
                blocks=blocks,
            )
        )
    return tabs
```

- [ ] **Step 4: Run, watch pass**

Run: `uv run pytest tests/unit/test_export_time_series.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add src/peerbench/export/data/time_series.py tests/unit/test_export_time_series.py
git commit -m "feat(export): build_time_series with stacked blocks per category"
```

---

## Task 13: writer.py — openpyxl per-tab writers

**Files:**
- Create: `src/peerbench/export/writer.py`

The writer is mostly mechanical openpyxl wiring. No unit tests at this layer — the integration test in Task 16 round-trips the whole workbook and verifies cell values, formats, and frozen panes. Style + structure issues that slip through static review get caught there.

- [ ] **Step 1: Write the file**

```python
"""openpyxl writer.

Consumes a WorkbookBundle and writes a .xlsx file. The writer owns ALL
openpyxl interaction; builders are pure-Python and never import openpyxl.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from openpyxl import Workbook
from openpyxl.styles import Alignment
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from peerbench.export.data.types import (
    CompSheetTab,
    CoverTab,
    MethodologyTab,
    RestatementTab,
    SummaryTab,
    TimeSeriesTab,
    WorkbookBundle,
)
from peerbench.export.format import (
    EM_DASH,
    format_delta_bps,
    format_fact_value,
    format_ratio_for_cell,
)
from peerbench.export.quartile import (
    bucket_for_cell,
    compute_quartile_cutoffs,
)
from peerbench.export import style as st


def write_workbook(bundle: WorkbookBundle, out_path: Path) -> Path:
    wb = Workbook()
    # Replace the default sheet with our Cover.
    wb.remove(wb.active)  # type: ignore[arg-type]
    _write_cover(wb, bundle.cover)
    _write_summary(wb, bundle.summary)
    for sheet in bundle.comp_sheets:
        _write_comp_sheet(wb, sheet)
    for ts in bundle.time_series:
        _write_time_series(wb, ts)
    if bundle.restatement_log is not None:
        _write_restatement(wb, bundle.restatement_log)
    if bundle.methodology is not None:
        _write_methodology(wb, bundle.methodology)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out_path)
    return out_path


# ---------------------------------------------------------------------------
# Cover
# ---------------------------------------------------------------------------

def _write_cover(wb: Workbook, cover: CoverTab) -> None:
    ws = wb.create_sheet("Cover")
    ws["A1"] = "Peerbench — Bank Peer Benchmarking"
    ws["A1"].font = st.FONT_TITLE
    ws["A2"] = f"{cover.anchor_name} · Cert {cover.anchor_cert}"
    ws["A2"].font = st.FONT_BODY_BOLD
    ws["A3"] = f"As of {cover.quarter_end}"
    ws["A5"] = (
        f"Generated {cover.generated_at.strftime('%Y-%m-%d %H:%M UTC')} "
        f"from data ingested through {cover.data_vintage}"
    )
    ws["A7"] = "Workbook contents:"
    ws["A7"].font = st.FONT_BODY_BOLD
    contents = [
        ("Summary", "all 30 ratios, anchor + peers, latest quarter"),
        ("Comp Sheets", "one tab per peer, side-by-side I/S + B/S + ratios"),
        ("Time Series", "8 quarters by ratio category"),
        ("Restatement Log", "facts revised by FDIC affecting workbook ratios"),
        ("Methodology", "formulas, sources, regulatory thresholds"),
    ]
    for i, (label, desc) in enumerate(contents):
        ws.cell(row=8 + i, column=1, value=f"• {label} — {desc}")
    ws["A14"] = "Data sources: FDIC BankFind API, FFIEC CDR bulk files."
    ws["A15"] = "Restatements detected automatically; see Restatement Log tab."
    next_row = 17
    for note in cover.notes:
        cell = ws.cell(row=next_row, column=1, value=note)
        cell.font = st.FONT_BODY_BOLD
        next_row += 1
    ws.column_dimensions["A"].width = 100


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def _write_summary(wb: Workbook, summary: SummaryTab) -> None:
    ws = wb.create_sheet("Summary")
    cols = summary.institution_columns
    n_inst = len(cols)
    # Layout:
    #   A: Category, B: Ratio, C..C+N-1: institutions, then median/rank/delta.
    header_row1 = ["Category", "Ratio"]
    header_row2 = ["", ""]
    for cert, name in cols:
        header_row1.append(name)
        header_row2.append(f"Cert {cert}")
    header_row1.extend(["Peer median", "Anchor rank", "Δ vs median"])
    header_row2.extend(["", "", ""])

    for col_idx, val in enumerate(header_row1, start=1):
        cell = ws.cell(row=1, column=col_idx, value=val)
        cell.font = st.FONT_HEADER
        cell.fill = st.FILL_HEADER
        cell.alignment = st.ALIGN_CENTER
    for col_idx, val in enumerate(header_row2, start=1):
        cell = ws.cell(row=2, column=col_idx, value=val)
        cell.font = st.FONT_BODY
        cell.alignment = st.ALIGN_CENTER

    current_row = 3
    last_category: str | None = None
    median_col = 2 + n_inst + 1
    rank_col = median_col + 1
    delta_col = rank_col + 1
    for row_data in summary.rows:
        if row_data.category != last_category:
            cat_cell = ws.cell(row=current_row, column=1, value=row_data.category)
            cat_cell.font = st.FONT_SECTION_HEADER
            cat_cell.fill = st.FILL_SECTION_HEADER
            ws.merge_cells(
                start_row=current_row, end_row=current_row,
                start_column=1, end_column=delta_col,
            )
            current_row += 1
            last_category = row_data.category
        ws.cell(row=current_row, column=1, value="")  # category col blank under header
        ws.cell(row=current_row, column=2, value=row_data.display_name).font = st.FONT_BODY

        # Peer values: collect numeric peer-only values for quartile cutoffs.
        peer_numeric: list[Decimal | None] = []
        for cert, _ in cols[1:]:  # skip anchor
            peer_numeric.append(row_data.peer_values.get(cert))
        cutoffs = compute_quartile_cutoffs(peer_numeric)

        for inst_idx, (cert, _) in enumerate(cols):
            col_idx = 3 + inst_idx
            value = (
                row_data.anchor_value if inst_idx == 0
                else row_data.peer_values.get(cert)
            )
            cell = ws.cell(row=current_row, column=col_idx,
                           value=format_ratio_for_cell(value))
            cell.number_format = st.NUMFMT_PERCENT
            cell.alignment = st.ALIGN_RIGHT
            # Tinting precedence: regulatory red > amber > quartile > anchor.
            fill = _summary_cell_fill(
                value=value,
                is_anchor=inst_idx == 0,
                amber_pct=row_data.amber_pct,
                red_pct=row_data.red_pct,
                cutoffs=cutoffs,
                direction=row_data.direction,
            )
            if fill is not None:
                cell.fill = fill

        median_cell = ws.cell(
            row=current_row, column=median_col,
            value=format_ratio_for_cell(row_data.peer_median),
        )
        median_cell.number_format = st.NUMFMT_PERCENT
        median_cell.alignment = st.ALIGN_RIGHT

        rank_cell = ws.cell(
            row=current_row, column=rank_col,
            value=row_data.anchor_rank if row_data.anchor_rank is not None else None,
        )
        rank_cell.number_format = st.NUMFMT_INTEGER
        rank_cell.alignment = st.ALIGN_RIGHT

        ws.cell(
            row=current_row, column=delta_col,
            value=format_delta_bps(row_data.anchor_value, row_data.peer_median),
        ).alignment = st.ALIGN_RIGHT
        current_row += 1

    ws.freeze_panes = "C3"
    ws.column_dimensions["A"].width = 24
    ws.column_dimensions["B"].width = 36
    for i in range(3, 3 + n_inst + 3):
        ws.column_dimensions[get_column_letter(i)].width = 14


def _summary_cell_fill(
    *,
    value: Decimal | None,
    is_anchor: bool,
    amber_pct: Decimal | None,
    red_pct: Decimal | None,
    cutoffs,
    direction: str,
):
    from peerbench.export.style import (
        FILL_ANCHOR, FILL_QUARTILE_BOTTOM, FILL_QUARTILE_TOP,
        FILL_THRESHOLD_AMBER, FILL_THRESHOLD_RED,
    )
    if value is not None:
        if red_pct is not None and value >= red_pct:
            return FILL_THRESHOLD_RED
        if amber_pct is not None and value >= amber_pct:
            return FILL_THRESHOLD_AMBER
        if not is_anchor:
            bucket = bucket_for_cell(value, cutoffs, direction)
            if bucket == "top":
                return FILL_QUARTILE_TOP
            if bucket == "bottom":
                return FILL_QUARTILE_BOTTOM
    if is_anchor:
        return FILL_ANCHOR
    return None


# ---------------------------------------------------------------------------
# Comp Sheet
# ---------------------------------------------------------------------------

def _write_comp_sheet(wb: Workbook, sheet: CompSheetTab) -> None:
    ws = wb.create_sheet(sheet.sheet_name)
    ws["A1"] = f"{sheet.anchor_name} vs {sheet.peer_name} · {sheet.quarter_id}"
    ws["A1"].font = st.FONT_TITLE
    # Section A: Income statement.
    row = 3
    ws.cell(row=row, column=1, value="Income statement (YTD, $ thousands)").font = st.FONT_RATIO_NAME
    row += 1
    # Header row: empty | anchor (4 quarter cols) | peer (4 quarter cols) | Δ
    n_q = len(sheet.income_statement_quarters)
    ws.cell(row=row, column=1, value="").alignment = st.ALIGN_LEFT
    ws.cell(row=row, column=2, value=sheet.anchor_name).font = st.FONT_HEADER
    ws.cell(row=row, column=2 + n_q, value=sheet.peer_name).font = st.FONT_HEADER
    ws.cell(row=row, column=2 + 2 * n_q, value="Δ (current)").font = st.FONT_HEADER
    row += 1
    for q_idx, q in enumerate(sheet.income_statement_quarters):
        ws.cell(row=row, column=2 + q_idx, value=q).font = st.FONT_BODY_BOLD
        ws.cell(row=row, column=2 + n_q + q_idx, value=q).font = st.FONT_BODY_BOLD
    row += 1
    for line in sheet.income_statement:
        ws.cell(row=row, column=1, value=line.label).font = st.FONT_BODY
        for q_idx, v in enumerate(line.anchor_values):
            c = ws.cell(row=row, column=2 + q_idx, value=float(v) if v is not None else None)
            c.number_format = st.NUMFMT_CURRENCY
            c.alignment = st.ALIGN_RIGHT
        for q_idx, v in enumerate(line.peer_values):
            c = ws.cell(row=row, column=2 + n_q + q_idx, value=float(v) if v is not None else None)
            c.number_format = st.NUMFMT_CURRENCY
            c.alignment = st.ALIGN_RIGHT
        # Δ on current (last) quarter.
        a_curr = line.anchor_values[-1] if line.anchor_values else None
        p_curr = line.peer_values[-1] if line.peer_values else None
        delta = (
            float(a_curr - p_curr) if a_curr is not None and p_curr is not None
            else None
        )
        c = ws.cell(row=row, column=2 + 2 * n_q, value=delta)
        c.number_format = st.NUMFMT_CURRENCY
        c.alignment = st.ALIGN_RIGHT
        row += 1
    # Section B: Balance sheet.
    row += 1
    ws.cell(row=row, column=1, value="Balance sheet (period-end, $ thousands)").font = st.FONT_RATIO_NAME
    row += 1
    ws.cell(row=row, column=1, value="").font = st.FONT_HEADER
    ws.cell(row=row, column=2, value=sheet.anchor_name).font = st.FONT_HEADER
    ws.cell(row=row, column=3, value=sheet.peer_name).font = st.FONT_HEADER
    ws.cell(row=row, column=4, value="Δ").font = st.FONT_HEADER
    row += 1
    for line in sheet.balance_sheet:
        ws.cell(row=row, column=1, value=line.label)
        for col_idx, val in [(2, line.anchor_value), (3, line.peer_value)]:
            c = ws.cell(row=row, column=col_idx, value=float(val) if val is not None else None)
            c.number_format = st.NUMFMT_CURRENCY
            c.alignment = st.ALIGN_RIGHT
        delta = (
            float(line.anchor_value - line.peer_value)
            if line.anchor_value is not None and line.peer_value is not None
            else None
        )
        c = ws.cell(row=row, column=4, value=delta)
        c.number_format = st.NUMFMT_CURRENCY
        row += 1
    # Section C: Ratios block.
    row += 1
    ws.cell(row=row, column=1, value="Ratios").font = st.FONT_RATIO_NAME
    row += 1
    headers = ["Ratio", "Formula", sheet.anchor_name, sheet.peer_name, "Δ", "Direction"]
    for col_idx, h in enumerate(headers, start=1):
        cell = ws.cell(row=row, column=col_idx, value=h)
        cell.font = st.FONT_HEADER
        cell.fill = st.FILL_HEADER
    row += 1
    last_cat: str | None = None
    for r in sheet.ratios:
        if r.category != last_cat:
            cat_cell = ws.cell(row=row, column=1, value=r.category)
            cat_cell.font = st.FONT_SECTION_HEADER
            cat_cell.fill = st.FILL_SECTION_HEADER
            ws.merge_cells(start_row=row, end_row=row, start_column=1, end_column=6)
            row += 1
            last_cat = r.category
        ws.cell(row=row, column=1, value=r.display_name)
        ws.cell(row=row, column=2, value=r.formula).font = st.FONT_FORMULA_ITALIC
        a_cell = ws.cell(row=row, column=3, value=format_ratio_for_cell(r.anchor_value))
        a_cell.number_format = st.NUMFMT_PERCENT
        p_cell = ws.cell(row=row, column=4, value=format_ratio_for_cell(r.peer_value))
        p_cell.number_format = st.NUMFMT_PERCENT
        ws.cell(row=row, column=5, value=format_delta_bps(r.anchor_value, r.peer_value))
        direction_text = {
            "higher_is_positive": "Higher better",
            "higher_is_negative": "Lower better",
            "neutral": "Neutral",
        }[r.direction]
        ws.cell(row=row, column=6, value=direction_text)
        row += 1
    ws.freeze_panes = "B4"
    ws.column_dimensions["A"].width = 28
    for c in range(2, 12):
        ws.column_dimensions[get_column_letter(c)].width = 14


# ---------------------------------------------------------------------------
# Time series
# ---------------------------------------------------------------------------

def _write_time_series(wb: Workbook, tab: TimeSeriesTab) -> None:
    ws = wb.create_sheet(tab.sheet_name)
    row = 1
    for block in tab.blocks:
        # Title.
        ws.cell(row=row, column=1, value=block.display_name).font = st.FONT_RATIO_NAME
        row += 1
        # Formula text.
        ws.cell(row=row, column=1, value=block.formula).font = st.FONT_FORMULA_ITALIC
        row += 1
        # Headers.
        ws.cell(row=row, column=1, value="").font = st.FONT_HEADER
        for q_idx, q in enumerate(block.quarter_ids):
            cell = ws.cell(row=row, column=2 + q_idx, value=q)
            cell.font = st.FONT_HEADER
            cell.fill = st.FILL_HEADER
        row += 1
        # Per-quarter quartile cutoffs across the visible peer set (anchor incl).
        cutoffs_by_q = [
            compute_quartile_cutoffs([r[2][q_idx] for r in block.rows])
            for q_idx in range(len(block.quarter_ids))
        ]
        for inst_idx, (cert, name, values) in enumerate(block.rows):
            label_cell = ws.cell(row=row, column=1, value=name)
            if inst_idx == 0:
                label_cell.fill = st.FILL_ANCHOR
                label_cell.font = st.FONT_BODY_BOLD
            for q_idx, v in enumerate(values):
                cell = ws.cell(
                    row=row, column=2 + q_idx,
                    value=format_ratio_for_cell(v),
                )
                cell.number_format = st.NUMFMT_PERCENT
                cell.alignment = st.ALIGN_RIGHT
                if inst_idx == 0:
                    cell.fill = st.FILL_ANCHOR
                else:
                    bucket = bucket_for_cell(v, cutoffs_by_q[q_idx], block.direction)
                    if bucket == "top":
                        cell.fill = st.FILL_QUARTILE_TOP
                    elif bucket == "bottom":
                        cell.fill = st.FILL_QUARTILE_BOTTOM
            row += 1
        row += 1  # blank spacer
    ws.freeze_panes = "B1"
    ws.column_dimensions["A"].width = 28
    for c in range(2, 12):
        ws.column_dimensions[get_column_letter(c)].width = 12


# ---------------------------------------------------------------------------
# Restatement Log
# ---------------------------------------------------------------------------

def _write_restatement(wb: Workbook, tab: RestatementTab) -> None:
    ws = wb.create_sheet("Restatement Log")
    headers = [
        "Detected at", "Cert", "Bank", "Quarter", "Field",
        "Old value", "New value", "Δ", "Affected ratios",
    ]
    for col_idx, h in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col_idx, value=h)
        cell.font = st.FONT_HEADER
        cell.fill = st.FILL_HEADER
    if not tab.rows:
        ws.cell(row=2, column=1, value="No restatements affecting workbook ratios.").font = st.FONT_FORMULA_ITALIC
    else:
        for row_idx, r in enumerate(tab.rows, start=2):
            ws.cell(row=row_idx, column=1, value=r.detected_at.strftime("%Y-%m-%d"))
            ws.cell(row=row_idx, column=2, value=r.cert)
            ws.cell(row=row_idx, column=3, value=r.bank_name)
            ws.cell(row=row_idx, column=4, value=r.quarter_id)
            ws.cell(row=row_idx, column=5, value=r.field_code)
            ws.cell(row=row_idx, column=6, value=format_fact_value(r.old_value)).alignment = st.ALIGN_RIGHT
            ws.cell(row=row_idx, column=7, value=format_fact_value(r.new_value)).alignment = st.ALIGN_RIGHT
            delta = (
                r.new_value - r.old_value
                if r.old_value is not None and r.new_value is not None
                else None
            )
            ws.cell(row=row_idx, column=8, value=format_fact_value(delta)).alignment = st.ALIGN_RIGHT
            ws.cell(row=row_idx, column=9, value=", ".join(r.affected_ratios))
    ws.freeze_panes = "A2"
    widths = [14, 8, 28, 10, 14, 14, 14, 12, 32]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w


# ---------------------------------------------------------------------------
# Methodology
# ---------------------------------------------------------------------------

def _write_methodology(wb: Workbook, tab: MethodologyTab) -> None:
    ws = wb.create_sheet("Methodology")
    ws["A1"] = "Methodology"
    ws["A1"].font = st.FONT_TITLE
    row = 3
    for note in tab.intro_notes:
        ws.cell(row=row, column=1, value=note.label).font = st.FONT_BODY_BOLD
        ws.cell(row=row, column=2, value=note.text).alignment = Alignment(wrap_text=True)
        row += 1
    row += 1
    for block in tab.blocks:
        ws.cell(row=row, column=1, value=block.display_name).font = st.FONT_RATIO_NAME
        ws.merge_cells(start_row=row, end_row=row, start_column=1, end_column=4)
        row += 1
        keys: list[tuple[str, str | None]] = [
            ("Category", block.category),
            ("Formula", block.formula),
            ("Source fields", ", ".join(block.source_fields) or EM_DASH),
            ("Annualization", block.annualization),
            ("Basis", block.basis),
            ("FDIC pre-computed", block.fdic_precomputed or EM_DASH),
            ("Regulatory threshold", block.regulatory_threshold or EM_DASH),
            ("Notes", block.notes or EM_DASH),
        ]
        for label, value in keys:
            ws.cell(row=row, column=1, value=label).font = st.FONT_BODY_BOLD
            ws.cell(row=row, column=2, value=value).alignment = Alignment(wrap_text=True)
            row += 1
        row += 1  # spacer
    ws.freeze_panes = "A2"
    ws.column_dimensions["A"].width = 22
    ws.column_dimensions["B"].width = 80
```

- [ ] **Step 2: Smoke import**

Run: `uv run python -c "from peerbench.export.writer import write_workbook; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 3: Type-check**

Run: `uv run pyright src/peerbench/export/writer.py`
Expected: 0 errors.

- [ ] **Step 4: Commit**

```bash
git add src/peerbench/export/writer.py
git commit -m "feat(export): openpyxl writer for all six tab kinds"
```

---

## Task 14: workbook.py — run_export orchestration

**Files:**
- Modify: `src/peerbench/export/workbook.py`

The orchestrator pulls all DB rows for the workbook in one place, hands typed inputs to each builder, packs them into a `WorkbookBundle`, and calls `write_workbook`.

- [ ] **Step 1: Replace the stub**

```python
"""Workbook orchestration: pull DB rows, build typed payloads, write file."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from peerbench.db import Fact, Institution, QualityLog, Quarter, Ratio, RatioDef
from peerbench.export.data.comp_sheet import build_comp_sheets
from peerbench.export.data.cover import build_cover
from peerbench.export.data.methodology import build_methodology
from peerbench.export.data.restatement import build_restatement_log
from peerbench.export.data.summary import build_summary
from peerbench.export.data.time_series import build_time_series
from peerbench.export.data.types import WorkbookBundle
from peerbench.export.writer import write_workbook

REPO_ROOT = Path(__file__).resolve().parents[3]
FIELD_DEPS_PATH = REPO_ROOT / "web" / "lib" / "ratio-field-deps.generated.json"

TIME_SERIES_WINDOW = 8


def run_export(
    session: Session,
    *,
    anchor_cert: int,
    quarter_id: str,
    out_dir: Path,
) -> Path:
    """Generate a comp workbook for `anchor_cert` × `quarter_id` and return the path written.

    Raises ValueError on unknown anchor or quarter.
    """
    quarter = session.get(Quarter, quarter_id)
    if quarter is None:
        recent = session.scalars(
            select(Quarter.quarter_id).order_by(Quarter.quarter_id.desc()).limit(8)
        ).all()
        raise ValueError(
            f"unknown quarter_id={quarter_id!r}; recent: {list(recent)}"
        )
    anchor = session.get(Institution, anchor_cert)
    if anchor is None:
        raise ValueError(f"unknown anchor cert={anchor_cert}")

    peers = list(
        session.scalars(
            select(Institution).where(
                Institution.active.is_(True),
                Institution.cert != anchor_cert,
            )
        ).all()
    )
    peers.sort(key=lambda i: i.name)

    # Time-series window: latest 8 quarters present in `quarters` table,
    # not after the workbook quarter.
    window_quarters = list(
        session.scalars(
            select(Quarter.quarter_id)
            .where(Quarter.quarter_id <= quarter_id)
            .order_by(Quarter.quarter_id.desc())
            .limit(TIME_SERIES_WINDOW)
        ).all()
    )
    window_quarters.sort()  # oldest first
    income_statement_quarters = window_quarters[-4:] if len(window_quarters) >= 4 else window_quarters

    cert_set = {anchor_cert, *(p.cert for p in peers)}

    # Ratios: cert × ratio_id for the workbook quarter, plus the full window
    # for time series.
    ratio_rows_window = list(
        session.execute(
            select(Ratio.cert, Ratio.quarter_id, Ratio.ratio_id, Ratio.value, Ratio.data_quality)
            .where(Ratio.cert.in_(cert_set))
            .where(Ratio.quarter_id.in_(window_quarters))
        ).all()
    )
    ratios_for_quarter: dict[int, dict[str, Decimal | None]] = {c: {} for c in cert_set}
    ratios_full: dict[int, dict[tuple[str, str], Decimal | None]] = {c: {} for c in cert_set}
    suppressed: set[tuple[int, str]] = set()
    for cert, qid, rid, value, dq in ratio_rows_window:
        ratios_full[cert][(qid, rid)] = value
        if qid == quarter_id:
            ratios_for_quarter[cert][rid] = value
            if dq == "suppressed":
                suppressed.add((cert, rid))

    # Facts for Comp Sheet I/S (4 quarters) + B/S (workbook quarter).
    fact_quarters = set(income_statement_quarters) | {quarter_id}
    fact_rows = list(
        session.execute(
            select(Fact.cert, Fact.quarter_id, Fact.field_code, Fact.value)
            .where(Fact.cert.in_(cert_set))
            .where(Fact.quarter_id.in_(fact_quarters))
        ).all()
    )
    facts: dict[tuple[int, str], dict[str, Decimal | None]] = {}
    for cert, qid, code, value in fact_rows:
        facts.setdefault((cert, qid), {})[code] = value

    ratio_defs = list(session.scalars(select(RatioDef)).all())
    field_deps = json.loads(FIELD_DEPS_PATH.read_text(encoding="utf-8"))

    # Restatement events within the time-series window.
    restatement_events = [
        {
            "detected_at": ev.detected_at,
            "cert": ev.cert,
            "quarter_id": ev.quarter_id,
            "field_code": ev.field_code,
            "old_value": ev.old_value,
            "new_value": ev.new_value,
        }
        for ev in session.scalars(
            select(QualityLog).where(QualityLog.event_type == "restated")
        ).all()
        if ev.cert in cert_set
    ]
    bank_names = {anchor_cert: anchor.name, **{p.cert: p.name for p in peers}}

    # Build typed payloads.
    anchor_pair = (anchor_cert, anchor.name)
    peer_pairs = [(p.cert, p.name) for p in peers]

    cover = build_cover(
        anchor_cert=anchor_cert,
        anchor_name=anchor.name,
        quarter_id=quarter_id,
        quarter_end_date=quarter.report_date,
        generated_at=datetime.now(UTC),
        data_vintage=quarter.ingest_at,
        anchor_has_no_ratios=not ratios_for_quarter.get(anchor_cert),
        active_peer_count=len(peers),
    )
    summary = build_summary(
        anchor=anchor_pair, peers=peer_pairs,
        ratio_defs=ratio_defs, ratios_by_cert=ratios_for_quarter,
        suppressed=suppressed,
    )
    comp_sheets = build_comp_sheets(
        anchor=anchor_pair, peers=peer_pairs,
        quarter_id=quarter_id,
        income_statement_quarter_ids=income_statement_quarters,
        facts_by_cert_quarter=facts,
        ratios_by_cert=ratios_for_quarter,
        ratio_defs=ratio_defs,
    )
    time_series = build_time_series(
        anchor=anchor_pair, peers=peer_pairs,
        quarter_ids=window_quarters,
        ratios_by_cert_quarter=ratios_full,
        ratio_defs=ratio_defs,
    )
    restatement_log = build_restatement_log(
        restatement_events,
        bank_names=bank_names,
        field_deps=field_deps,
        window=set(window_quarters),
    )
    methodology = build_methodology(ratio_defs, field_deps=field_deps)

    bundle = WorkbookBundle(
        cover=cover,
        summary=summary,
        comp_sheets=comp_sheets,
        time_series=time_series,
        restatement_log=restatement_log,
        methodology=methodology,
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    if out_dir.is_file():  # paranoia — Typer should have caught this
        raise ValueError(f"output path is a file, not a directory: {out_dir}")
    out_path = out_dir / f"peerbench_{anchor_cert}_{quarter_id}.xlsx"
    write_workbook(bundle, out_path)
    return out_path
```

- [ ] **Step 2: Smoke import**

Run: `uv run python -c "from peerbench.export import run_export; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 3: Type-check**

Run: `uv run pyright src/peerbench/export/workbook.py`
Expected: 0 errors.

- [ ] **Step 4: Commit**

```bash
git add src/peerbench/export/workbook.py
git commit -m "feat(export): run_export orchestration"
```

---

## Task 15: CLI command — `peerbench export`

**Files:**
- Modify: `src/peerbench/cli.py`

- [ ] **Step 1: Add the command**

Append to `src/peerbench/cli.py`, after the existing `validate` command:

```python
@app.command("export")
def export_cmd(
    quarter: Annotated[
        str,
        typer.Option("--quarter", help="Quarter ID 'YYYY-Qn' (e.g. 2025-Q4)"),
    ],
    output: Annotated[
        Path,
        typer.Option("--output", help="Output directory; created if missing"),
    ],
    anchor: Annotated[
        int,
        typer.Option("--anchor", help="FDIC certificate number"),
    ] = 4063,
) -> None:
    """Generate the Phase 4.2 Excel comp workbook for an anchor × quarter."""
    from peerbench.export import run_export

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    if output.exists() and output.is_file():
        typer.echo(f"--output must be a directory, not a file: {output}", err=True)
        raise typer.Exit(code=2)
    with get_session() as session:
        try:
            out_path = run_export(
                session,
                anchor_cert=anchor,
                quarter_id=quarter,
                out_dir=output,
            )
        except ValueError as e:
            typer.echo(str(e), err=True)
            raise typer.Exit(code=2) from None
    typer.echo(f"wrote {out_path}")
```

- [ ] **Step 2: Smoke `--help`**

Run: `uv run peerbench export --help`
Expected: help text listing `--quarter`, `--output`, `--anchor`.

- [ ] **Step 3: Commit**

```bash
git add src/peerbench/cli.py
git commit -m "feat(cli): peerbench export command"
```

---

## Task 16: Integration test — round-trip a real .xlsx

**Files:**
- Create: `tests/integration/test_export_workbook.py`

This is the structural-correctness gate: builds a fake but realistic dataset in an in-memory SQLite DB, runs `run_export`, opens the resulting file with openpyxl, and asserts the most important cells / formats / freeze panes. Catches both data-shape bugs and openpyxl-wiring bugs in one shot.

- [ ] **Step 1: Write the test**

```python
"""Round-trip integration: build a real .xlsx and read it back."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from openpyxl import load_workbook
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from peerbench.db import (
    Base, Fact, Institution, QualityLog, Quarter, Ratio, RatioDef,
)
from peerbench.export import run_export


@pytest.mark.integration
def test_export_writes_six_tab_kinds(tmp_path: Path) -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        _seed(session)
        out_path = run_export(
            session,
            anchor_cert=4063,
            quarter_id="2025-Q4",
            out_dir=tmp_path,
        )

    assert out_path.exists()
    wb = load_workbook(out_path)
    names = wb.sheetnames
    assert "Cover" in names
    assert "Summary" in names
    assert "Restatement Log" in names
    assert "Methodology" in names
    # Comp Sheets: at least one peer tab named after a seeded peer.
    assert any(n in {"Peer A", "Peer B"} for n in names)
    # Time series: at least one category tab.
    assert "Profitability" in names

    # Summary freeze pane.
    summary = wb["Summary"]
    assert summary.freeze_panes == "C3"
    # First data row third column should hold the anchor NIM value (3.42%).
    # Walk past the section header to find it: scan for the row whose
    # column 2 is the ratio display name.
    for row in summary.iter_rows(min_row=3, max_row=15, values_only=False):
        if row[1].value == "Net Interest Margin":
            assert row[2].value == pytest.approx(0.0342, abs=1e-6)
            assert row[2].number_format == "0.00%;(0.00%)"
            break
    else:
        pytest.fail("Net Interest Margin row not found on Summary")

    # Restatement Log row 2 has the seeded event.
    rl = wb["Restatement Log"]
    assert rl["E2"].value == "NETINC"

    # Methodology has at least one block with the seeded display name.
    meth = wb["Methodology"]
    found = False
    for row in meth.iter_rows(values_only=True):
        if any(v == "Net Interest Margin" for v in row if v is not None):
            found = True
            break
    assert found, "Methodology missing NIM block"


def _seed(session: Session) -> None:
    # Institutions: anchor + 4 peers (need ≥4 non-suppressed for quartile cutoffs).
    session.add(Institution(cert=4063, name="MidFirst", active=True))
    session.add(Institution(cert=8001, name="Peer A", active=True))
    session.add(Institution(cert=8002, name="Peer B", active=True))
    session.add(Institution(cert=8003, name="Peer C", active=True))
    session.add(Institution(cert=8004, name="Peer D", active=True))
    # Quarters: 8 quarters back from 2025-Q4.
    quarter_ids = [
        "2024-Q1", "2024-Q2", "2024-Q3", "2024-Q4",
        "2025-Q1", "2025-Q2", "2025-Q3", "2025-Q4",
    ]
    for qid in quarter_ids:
        year, q = int(qid[:4]), int(qid[-1])
        session.add(Quarter(
            quarter_id=qid, year=year, quarter=q,
            report_date=date(year, q * 3, 30 if q != 1 else 31),
            ingest_at=datetime(2026, 5, 22, tzinfo=UTC),
            source="fdic_api",
        ))
    # Ratio defs: one minimal NIM row covers Cover, Summary, Comp, TS, Methodology.
    session.add(RatioDef(
        ratio_id="nim",
        display_name="Net Interest Margin",
        category="profitability",
        numerator_formula="Net interest income",
        denominator_formula="Avg earning assets",
        annualize=True,
        avg_or_eop="AVG",
        fdic_precomputed_code="NIMY",
        ubpr_concept=None,
        regulatory_threshold=None,
        suppress_when=None,
        notes=None,
    ))
    # Ratios: 5 institutions × 8 quarters.
    anchor_vals = {
        "2025-Q4": Decimal("0.0342"),
    }
    peer_offsets = {8001: Decimal("-0.002"), 8002: Decimal("-0.004"),
                    8003: Decimal("-0.006"), 8004: Decimal("-0.008")}
    for qid in quarter_ids:
        anchor_val = anchor_vals.get(qid, Decimal("0.0320"))
        session.add(Ratio(
            cert=4063, quarter_id=qid, ratio_id="nim",
            value=anchor_val, formula_version="v1", data_quality="ok",
            computed_at=datetime(2026, 5, 22, tzinfo=UTC),
        ))
        for cert, offset in peer_offsets.items():
            session.add(Ratio(
                cert=cert, quarter_id=qid, ratio_id="nim",
                value=anchor_val + offset, formula_version="v1", data_quality="ok",
                computed_at=datetime(2026, 5, 22, tzinfo=UTC),
            ))
    # A few facts for the Comp Sheet I/S + B/S.
    income_codes = ["INTINC", "EINTEXP", "NIM", "ELNATR", "NONII", "NONIX", "NETINC"]
    balance_codes = ["ASSET", "LNLSGR", "SC", "CHBAL", "DEP", "LIAB", "EQ"]
    for cert in [4063, 8001, 8002, 8003, 8004]:
        for code in income_codes + balance_codes:
            for qid in quarter_ids:
                session.add(Fact(
                    cert=cert, quarter_id=qid, field_code=code,
                    value=Decimal("1000000"),
                    first_seen_at=datetime(2026, 5, 22, tzinfo=UTC),
                    last_updated_at=datetime(2026, 5, 22, tzinfo=UTC),
                ))
    # One restatement event affecting NIM via NETINC (… field-deps JSON
    # already maps `nim` to a set including NIM/NIM-style fields; pick a
    # code we know is in the workbook ratios' deps).
    session.add(QualityLog(
        cert=4063, quarter_id="2025-Q3", field_code="NETINC",
        event_type="restated",
        old_value=Decimal("100"), new_value=Decimal("120"),
        detected_at=datetime(2026, 5, 22, tzinfo=UTC),
    ))
    session.commit()
```

- [ ] **Step 2: Run the integration test**

Run: `uv run pytest tests/integration/test_export_workbook.py -v -m integration`
Expected: PASS.

- [ ] **Step 3: Inspect a generated file (manual)**

```bash
mkdir -p output
uv run peerbench export --quarter 2025-Q4 --output ./output/
open output/peerbench_4063_2025-Q4.xlsx  # macOS
```

Spot-check:
- All six tab kinds visible in the bottom strip.
- Summary anchor column tinted navy.
- At least one peer cell tinted green or red.
- Restatement Log has rows.
- Methodology has all 30 ratio blocks.

If anything looks off, fix and re-run the integration test.

- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_export_workbook.py
git commit -m "test(export): integration test round-trips a real .xlsx"
```

---

## Task 17: Final smoke + reviewer subagent

- [ ] **Step 1: Full test sweep**

```bash
uv run pytest -v
uv run ruff format src tests
uv run ruff check src tests
uv run pyright src/peerbench/export
```

Expected: pytest green, no ruff complaints, pyright clean on the new package.

- [ ] **Step 2: Dispatch reviewer subagent**

Use the project's `reviewer` sub-agent (see `CLAUDE.md`) against the diff for this branch. If you're using subagent-driven execution, this happens automatically.

- [ ] **Step 3: Generate a real workbook against the production DB and sanity-check**

```bash
uv run peerbench export --quarter 2025-Q4 --output ./output/
open output/peerbench_4063_2025-Q4.xlsx
```

Verify the Summary tab values match the dashboard at https://peerbench-web.vercel.app/ for 2025-Q4 (eyeball the anchor row).

- [ ] **Step 4: Open a PR**

```bash
gh pr create --title "Phase 4.2: Excel comp workbook export" --body "$(cat <<'EOF'
## Summary
- New `peerbench export` CLI command emits a six-tab comp workbook
- Pure-function builders + typed payloads + single openpyxl writer
- Reads from `ratios`/`facts`/`quality_log`/`ratio_defs` — no formula logic in the export layer
- 30 ratios × all active peers × 8 quarters; Restatement Log + Methodology auto-populated

## Test plan
- [ ] `uv run pytest` green
- [ ] `uv run pyright src/peerbench/export` clean
- [ ] Manual workbook spot-check against dashboard for 2025-Q4

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Self-review checklist

After implementation:

1. **Spec coverage** — verified during plan writing. Every section of the spec maps to a task: Cover (T7), Summary (T10), Comp Sheets (T11), Time Series (T12), Restatement Log (T9), Methodology (T8); CLI (T15); style + format + directions + quartile (T2–T5); ELNATR pipeline change (T6); writer (T13); orchestration (T14); integration test (T16); reviewer + ship (T17).

2. **Placeholder scan** — no TBDs in the plan. Every code block is concrete.

3. **Type consistency** — `RatioDefLike` Protocol is reused across summary / comp_sheet / methodology (compatible attribute set); `TimeSeriesBlock.rows` shape `tuple[int, str, list[Decimal | None]]` is consistent in builder + writer; `direction_for` return type matches `quartile.bucket_for_cell`'s parameter.

4. **Open follow-ups from the spec** — explicitly tracked in the spec's "Open follow-ups" section (FDIC codes verified during plan-writing, plain-English meanings deferred to Phase 4.1, Cover hyperlinks/Windows compatibility/`top_loan_cat` time-series block are non-blocking polish).
