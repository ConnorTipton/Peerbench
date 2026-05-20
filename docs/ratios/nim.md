# Net Interest Margin (NIM)

This document is the template for the per-ratio worked-example docs. The
other 29 ratios are stubbed for Phase 2/4.

## What this ratio measures

NIM is what's left over after a bank pays for its funding. Out of every
dollar of earning assets (loans + securities), how many cents per year
does the bank actually net from spread income, after paying depositors
and bond holders? Higher is better, but a NIM that's *too* high may be
masking concentration risk or unsustainable funding cost.

Banks with heavy CRE or high-yield consumer portfolios run wide NIMs;
super-regional commercial banks with rate-sensitive deposit bases run
narrower NIMs. Peerbench reports NIM on a **non-tax-equivalent basis**
to match FDIC's `NIMY`; UBPR reports a tax-equivalent variant — see the
"Known divergence vs UBPR" section.

## Formula

```
nim = (NIM × annualize_factor) / ERNAST5
```

Registered handler (`src/peerbench/ratio_engine/handlers/profitability.py:16-21`):

```python
@ratio("nim", version="v1")
def compute_nim(f: FactView) -> Decimal:
    # Net interest margin = NIM (YTD $) × annualize / average earning assets.
    # Use FDIC's precomputed ERNAST5 when available; the field is itself the
    # 5-period YTD average. Non-tax-equivalent — UBPR NIM is TE.
    return f["NIM"] * f.annualize_factor() / f["ERNAST5"]
```

## FDIC field codes used

| Field | Meaning | Notes |
| --- | --- | --- |
| `NIM` | YTD net interest income, $ thousands | Confusingly named — this is the dollar income, not the ratio. The ratio is `NIMY`. |
| `ERNAST5` | 5-period YTD average earning assets, $ thousands | FDIC pre-averages this field for us. See "YTD averaging convention" below. |
| (implicit) `quarter_number` | 1, 2, 3, or 4 | Drives `FactView.annualize_factor()`. |

## YTD averaging convention

FDIC's YTD-average fields (`ASSET5`, `EQ5`, `ERNAST5`) are pre-averaged
over `quarter_number + 1` quarter-end observations:

| Quarter | Observations averaged | Periods |
| --- | --- | --- |
| Q1 | prior Dec + Mar | 2 |
| Q2 | prior Dec + Mar + Jun | 3 |
| Q3 | prior Dec + Mar + Jun + Sep | 4 |
| Q4 | prior Dec + Mar + Jun + Sep + Dec | 5 |

The compute layer requests a 5-period `FactView` (`load_fact_view(..., periods=5)`)
to support the longest case, then individual handlers use
`f.avg(field, periods=f.quarter_number + 1)` for fields they need to
average themselves. NIM specifically *doesn't* call `f.avg()` because
`ERNAST5` is already FDIC-averaged.

Why this matters: hardcoding `periods=5` would only be correct at Q4 —
for Q1 it would average 5 quarter-ends including 3 quarters of stale
data from prior calendar year. The `quarter_number + 1` rule is FDIC's
published convention.

## Annualization

YTD income statement values represent partial-year cumulative income, so
we annualize by `4 / quarter_number`:

| Quarter | Factor | Reasoning |
| --- | --- | --- |
| Q1 | ×4 | 3 months of income → multiply by 4 to project annual |
| Q2 | ×2 | 6 months → ×2 |
| Q3 | ×4/3 | 9 months → ×4/3 |
| Q4 | ×1 | 12 months = full year |

Implementation: `FactView.annualize_factor()` returns the right factor
based on `quarter_number`. Balance-sheet ratios skip annualization
(they're period-end snapshots, not flows).

## Decimal precision

Every intermediate is a Python `Decimal`. The contract test
`tests/contract/test_ratio_registry.py::TestNoFloatInValuePath` greps for
`float(` casts in `src/peerbench/{decimal_,ingest/fdic,ingest/upsert,
ratio_engine/*,validate}.py` and fails CI if any are found. The
discipline buys us exact arithmetic at full source-data precision —
that's why our NIM matches FDIC's `NIMY` to 14 decimal places (see
worked example below).

## Worked example — MidFirst (cert 4063), 2025-Q4

Raw facts pulled from `facts` table (values in $ thousands):

| Field | Value |
| --- | --- |
| `NIM` | 1,097,635 |
| `ERNAST5` | 37,976,318.4 |
| `INTINC` | 2,117,319 |
| `EINTEXP` | 1,019,684 |
| `ASSET` (EOP) | 41,367,487 |

(Side check that `NIM` ≈ `INTINC - EINTEXP`: 2,117,319 − 1,019,684 = 1,097,635. ✓)

### Step 1: annualization factor

Q4 → `4 / 4 = 1`. (YTD income already covers the full year.)

### Step 2: substitute into the formula

```
nim = NIM × annualize_factor / ERNAST5
    = 1,097,635 × 1 / 37,976,318.4
    = 1,097,635 / 37,976,318.4
    = 0.02890314401829957271476847529
```

### Step 3: compare to FDIC's pre-computed `NIMY`

FDIC reports `NIMY` in percent: **2.8903144018299574**.

Convert FDIC to fraction: `2.8903144018299574 / 100 = 0.028903144018299574`.

Diff: `|0.02890314401829957271476847529 − 0.028903144018299574| ≈ 1.3e-18` → **0.0 bps**.

Match to 14 decimal places. The `_29...` tail on our value comes from
Python `Decimal` keeping the full division precision; FDIC's `NIMY` is
truncated to 14 decimals in their JSON API response.

## Reproducing this calculation

```bash
uv run peerbench compute --cert 4063 --quarters 1
```

Outputs `2025-Q4: 27 ok, 3 partial, 0 suppressed`. To inspect the value:

```sql
SELECT value FROM ratios
 WHERE cert=4063 AND quarter_id='2025-Q4' AND ratio_id='nim';
-- 0.02890314401829957271476847529
```

## Known divergence vs UBPR

UBPR reports a **tax-equivalent** NIM: muni interest income is grossed
up to its pre-tax equivalent, since munis are federally tax-exempt and
banks effectively earn more economic yield than the stated coupon
suggests. Our `nim` does not gross up. Expect a **5–15 bp upward gap**
in UBPR vs Peerbench for banks with material muni holdings.

We match `NIMY` (which is also non-TE) to fractions of a bp; the gap is
strictly between Peerbench and UBPR, not between Peerbench and FDIC.

See [`docs/divergences.md`](../divergences.md) for the full divergence
catalog.
