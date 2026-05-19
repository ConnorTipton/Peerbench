"""Yield / cost ratios: yield_ea, cost_funds, nis.

`nis` duplicates the yield_ea - cost_funds calculation rather than reading
prior ratio results. Day 3 deliberate choice: avoids the RatioView indirection
the plan flagged as deferred work. Trade-off: if yield_ea or cost_funds
change, nis must change too. The contract test's AST-hash check makes this
visible at PR time.
"""

from __future__ import annotations

from decimal import Decimal

from peerbench.ratio_engine.fact_view import FactView
from peerbench.ratio_engine.registry import ratio


def _yield_ea(f: FactView) -> Decimal:
    return f["INTINC"] * f.annualize_factor() / f["ERNAST5"]


def _cost_funds(f: FactView) -> Decimal:
    # True cost of funds = total interest expense / average interest-bearing
    # liabilities. The FDIC API doesn't expose a pre-averaged IBL field, so
    # we approximate via DEPI (qtly interest-bearing deposits). FDIC's YTD
    # average uses quarter_number + 1 observations (prior Dec + current YTD
    # quarter-ends): 2/3/4/5 for Q1/Q2/Q3/Q4. Methodology gap: excludes other
    # borrowings — documented in Day 4 validation.
    return f["EINTEXP"] * f.annualize_factor() / f.avg("DEPI", periods=f.quarter_number + 1)


@ratio("yield_ea", version="v1")
def compute_yield_ea(f: FactView) -> Decimal:
    return _yield_ea(f)


@ratio("cost_funds", version="v1")
def compute_cost_funds(f: FactView) -> Decimal:
    return _cost_funds(f)


@ratio("nis", version="v1")
def compute_nis(f: FactView) -> Decimal:
    # Net interest spread = yield on earning assets - cost of funds.
    # Duplicated formula (see module docstring); the topological resolver
    # would let us read prior ratio results, but that's a Day 4+ refactor.
    return _yield_ea(f) - _cost_funds(f)
