"""Unit tests for liquidity ratio handlers.

Focus is on `htm_loss_t1`, which combines FDIC API (SCHA = HTM amortized
cost) with CDR-sourced fields (CDR_HTM_FAIRVAL = HTM fair value). Per
data/ratios.csv the ratio must clamp to zero in the gain case ("losses
only, not gains") — otherwise a falling-rate quarter inverts the risk
ranking.
"""

from __future__ import annotations

from decimal import Decimal

from peerbench.ratio_engine.fact_view import FactView
from peerbench.ratio_engine.handlers.liquidity import compute_htm_loss_t1


def _fv(**facts: Decimal) -> FactView:
    return FactView(
        cert=4063,
        quarter_id="2025-Q4",
        quarter_number=4,
        facts_by_period=(dict(facts),),
    )


def test_htm_loss_floored_at_zero_when_fair_value_exceeds_book() -> None:
    f = _fv(
        SCHA=Decimal("1000000"),
        CDR_HTM_FAIRVAL=Decimal("1100000"),
        RBCT1J=Decimal("500000"),
    )
    assert compute_htm_loss_t1(f) == Decimal("0")


def test_htm_loss_positive_when_portfolio_underwater() -> None:
    f = _fv(
        SCHA=Decimal("1100000"),
        CDR_HTM_FAIRVAL=Decimal("1000000"),
        RBCT1J=Decimal("1000000"),
    )
    assert compute_htm_loss_t1(f) == Decimal("0.1")


def test_htm_loss_zero_when_at_par() -> None:
    f = _fv(
        SCHA=Decimal("1000000"),
        CDR_HTM_FAIRVAL=Decimal("1000000"),
        RBCT1J=Decimal("500000"),
    )
    assert compute_htm_loss_t1(f) == Decimal("0")
