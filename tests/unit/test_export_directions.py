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
    assert len(RATIO_DIRECTIONS) == 30
