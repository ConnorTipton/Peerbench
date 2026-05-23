from __future__ import annotations

from decimal import Decimal

from peerbench.export.quartile import (
    QuartileCutoffs,
    bucket_for_cell,
    compute_quartile_cutoffs,
)


def test_compute_cutoffs_canonical_five_values() -> None:
    cutoffs = compute_quartile_cutoffs([Decimal(v) for v in (10, 20, 30, 40, 50)])
    assert cutoffs is not None
    assert cutoffs.q1 == Decimal(20)
    assert cutoffs.median == Decimal(30)
    assert cutoffs.q3 == Decimal(40)


def test_compute_cutoffs_returns_none_with_three_values() -> None:
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
    cutoffs = QuartileCutoffs(q1=Decimal(20), median=Decimal(30), q3=Decimal(40))
    assert bucket_for_cell(Decimal(50), cutoffs, "higher_is_negative") == "bottom"
    assert bucket_for_cell(Decimal(10), cutoffs, "higher_is_negative") == "top"


def test_bucket_neutral_returns_none() -> None:
    cutoffs = QuartileCutoffs(q1=Decimal(20), median=Decimal(30), q3=Decimal(40))
    assert bucket_for_cell(Decimal(50), cutoffs, "neutral") == "none"


def test_bucket_value_equal_to_q3_is_middle() -> None:
    cutoffs = QuartileCutoffs(q1=Decimal(20), median=Decimal(30), q3=Decimal(40))
    assert bucket_for_cell(Decimal(40), cutoffs, "higher_is_positive") == "middle"


def test_bucket_none_value() -> None:
    cutoffs = QuartileCutoffs(q1=Decimal(20), median=Decimal(30), q3=Decimal(40))
    assert bucket_for_cell(None, cutoffs, "higher_is_positive") == "none"


def test_bucket_none_cutoffs() -> None:
    assert bucket_for_cell(Decimal(50), None, "higher_is_positive") == "none"
