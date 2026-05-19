"""Profitability ratios: nim, roa, roe, eff_ratio, ppnr_assets.

Bodies filled in Day 3. The @ratio decorator captures the AST hash of each
function body now, so any body edit without a corresponding version bump
will be caught by tests/contract/test_ratio_registry.py.
"""

from __future__ import annotations

from decimal import Decimal

from peerbench.ratio_engine.fact_view import FactView
from peerbench.ratio_engine.registry import ratio


@ratio("nim", version="v1")
def compute_nim(f: FactView) -> Decimal:
    # Day 3: NIM = (NIM_YTD × annualize_factor) / avg(ERNAST, periods=5)
    raise NotImplementedError("nim handler body lands Day 3")


@ratio("roa", version="v1")
def compute_roa(f: FactView) -> Decimal:
    # Day 3: ROA = (NETINC × annualize_factor) / ASSET5
    raise NotImplementedError("roa handler body lands Day 3")


@ratio("roe", version="v1")
def compute_roe(f: FactView) -> Decimal:
    # Day 3: ROE = (NETINC × annualize_factor) / EQ5
    raise NotImplementedError("roe handler body lands Day 3")


@ratio("eff_ratio", version="v1")
def compute_eff_ratio(f: FactView) -> Decimal:
    # Day 3: Efficiency = NONIX / (NIM + NONII). FDIC EEFFR subtracts
    # intangibles amortization in the numerator — document the gap.
    raise NotImplementedError("eff_ratio handler body lands Day 3")


@ratio("ppnr_assets", version="v1")
def compute_ppnr_assets(f: FactView) -> Decimal:
    # Day 3: PPNR / Avg Assets = (NIM + NONII - NONIX) × annualize_factor / ASSET5
    raise NotImplementedError("ppnr_assets handler body lands Day 3")
