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
    assert format_ratio_for_cell(None) is None


def test_format_fact_value_thousands() -> None:
    assert format_fact_value(Decimal("1234567")) == "1,234,567"


def test_format_fact_value_none() -> None:
    assert format_fact_value(None) == EM_DASH


def test_format_fact_value_negative_parens() -> None:
    assert format_fact_value(Decimal("-500")) == "(500)"


def test_format_delta_bps_positive() -> None:
    assert format_delta_bps(Decimal("0.0350"), Decimal("0.0320")) == "+30 bps"


def test_format_delta_bps_negative() -> None:
    assert format_delta_bps(Decimal("0.0320"), Decimal("0.0350")) == "(30 bps)"


def test_format_delta_bps_none() -> None:
    assert format_delta_bps(None, Decimal("0.05")) == EM_DASH
    assert format_delta_bps(Decimal("0.05"), None) == EM_DASH
    assert format_delta_bps(None, None) == EM_DASH


def test_format_delta_bps_rounds_to_nearest_basis_point() -> None:
    assert format_delta_bps(Decimal("0.00500"), Decimal("0")) == "+50 bps"
    assert format_delta_bps(Decimal("0.000049"), Decimal("0")) == "+0 bps"
