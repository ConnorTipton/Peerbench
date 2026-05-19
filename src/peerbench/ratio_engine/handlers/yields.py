"""Yield / cost ratios: yield_ea, cost_funds, nis.

`nis` depends on the other two — see compute.RATIO_DEPENDENCIES.
"""

from __future__ import annotations

from decimal import Decimal

from peerbench.ratio_engine.fact_view import FactView
from peerbench.ratio_engine.registry import ratio


@ratio("yield_ea", version="v1")
def compute_yield_ea(f: FactView) -> Decimal:
    # Day 3: INTINC × annualize_factor / avg(ERNAST, periods=5)
    raise NotImplementedError("yield_ea handler body lands Day 3")


@ratio("cost_funds", version="v1")
def compute_cost_funds(f: FactView) -> Decimal:
    # Day 3: EINTEXP × annualize_factor / avg(interest-bearing liabs, periods=5)
    # Denominator must be composed from components — see ratios.csv notes.
    raise NotImplementedError("cost_funds handler body lands Day 3")


@ratio("nis", version="v1")
def compute_nis(f: FactView) -> Decimal:
    # Day 3: yield_ea - cost_funds. Topological resolver guarantees those
    # dependents are computed first. Open question per plan §5: keep as a
    # persisted ratio row or move to a SQL view.
    raise NotImplementedError("nis handler body lands Day 3")
