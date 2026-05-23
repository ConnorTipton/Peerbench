from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from peerbench.export.data.time_series import build_time_series


def test_build_time_series_one_tab_per_category() -> None:
    ratio_defs = [
        _def(
            "nim",
            "profitability",
            "Net Interest Margin",
            "Net interest income",
            "Avg earning assets",
        ),
        _def("eff_ratio", "profitability", "Efficiency Ratio", "NIE - amort", "NII + Non-int inc"),
        _def("loans_assets", "balance_sheet", "Loans / Assets", "Loans", "Assets"),
    ]
    anchor = (4063, "MidFirst")
    peers = [(110, "BOK")]
    quarter_ids = [
        "2024-Q1",
        "2024-Q2",
        "2024-Q3",
        "2024-Q4",
        "2025-Q1",
        "2025-Q2",
        "2025-Q3",
        "2025-Q4",
    ]
    ratios = {
        4063: {(q, "nim"): Decimal("0.035") for q in quarter_ids},
        110: {(q, "nim"): Decimal("0.030") for q in quarter_ids},
    }
    tabs = build_time_series(
        anchor=anchor,
        peers=peers,
        quarter_ids=quarter_ids,
        ratios_by_cert_quarter=ratios,
        ratio_defs=ratio_defs,
    )
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
        anchor=anchor,
        peers=peers,
        quarter_ids=quarter_ids,
        ratios_by_cert_quarter=ratios,
        ratio_defs=ratio_defs,
    )
    block = tabs[0].blocks[0]
    assert block.rows[0][0] == 4063
    assert block.rows[0][1] == "MidFirst"


def test_build_time_series_8_quarters_oldest_first() -> None:
    ratio_defs = [_def("nim", "profitability", "NIM", "x", "y")]
    quarter_ids = [
        "2024-Q1",
        "2024-Q2",
        "2024-Q3",
        "2024-Q4",
        "2025-Q1",
        "2025-Q2",
        "2025-Q3",
        "2025-Q4",
    ]
    tabs = build_time_series(
        anchor=(4063, "MidFirst"),
        peers=[],
        quarter_ids=quarter_ids,
        ratios_by_cert_quarter={4063: {}},
        ratio_defs=ratio_defs,
    )
    assert tabs[0].blocks[0].quarter_ids == quarter_ids


def test_build_time_series_missing_value_renders_none() -> None:
    ratio_defs = [_def("nim", "profitability", "NIM", "x", "y")]
    quarter_ids = ["2025-Q3", "2025-Q4"]
    ratios = {4063: {("2025-Q4", "nim"): Decimal("0.035")}}
    tabs = build_time_series(
        anchor=(4063, "MidFirst"),
        peers=[],
        quarter_ids=quarter_ids,
        ratios_by_cert_quarter=ratios,
        ratio_defs=ratio_defs,
    )
    values = tabs[0].blocks[0].rows[0][2]
    assert values[0] is None
    assert values[1] == Decimal("0.035")


@dataclass
class _D:
    ratio_id: str
    display_name: str
    category: str
    numerator_formula: str
    denominator_formula: str


def _def(rid: str, category: str, name: str, num: str, den: str) -> _D:
    return _D(rid, name, category, num, den)
