from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from peerbench.export.data.comp_sheet import (
    BALANCE_SHEET_LINES,
    INCOME_STATEMENT_LINES,
    build_comp_sheets,
    sanitize_sheet_name,
)


def test_sanitize_sheet_name_strips_invalid_chars() -> None:
    assert sanitize_sheet_name("Foo/Bar*Baz[1]") == "FooBarBaz1"


def test_sanitize_sheet_name_truncates_to_31_chars() -> None:
    name = "A" * 50
    assert len(sanitize_sheet_name(name)) == 31


def test_sanitize_sheet_name_collision_appends_suffix() -> None:
    used: set[str] = set()
    a = sanitize_sheet_name("BOK Financial Corp Inc.", used=used)
    used.add(a)
    b = sanitize_sheet_name("BOK Financial Corp Inc.", used=used)
    used.add(b)
    assert a != b
    assert b.startswith(a[:29])


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
    assert codes == ["INTINC", "EINTEXP", "NIM", "ELNATR", "NONII", "NONIX", "NETINC"]


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
    ratios = {
        4063: {"nim": Decimal("0.035")},
        110: {"nim": Decimal("0.030")},
        4214: {"nim": Decimal("0.028")},
    }
    ratio_defs = [
        _def(
            "nim",
            "profitability",
            "Net Interest Margin",
            "Net interest income",
            "Average earning assets",
        )
    ]
    sheets = build_comp_sheets(
        anchor=anchor,
        peers=peers,
        quarter_id="2025-Q4",
        income_statement_quarter_ids=["2025-Q1", "2025-Q2", "2025-Q3", "2025-Q4"],
        facts_by_cert_quarter={},
        ratios_by_cert=ratios,
        ratio_defs=ratio_defs,
    )
    assert len(sheets) == 2
    bok = next(s for s in sheets if s.peer_cert == 110)
    assert bok.anchor_cert == 4063
    assert bok.ratios[0].anchor_value == Decimal("0.035")
    assert bok.ratios[0].peer_value == Decimal("0.030")


def test_build_comp_sheets_picks_correct_field_values() -> None:
    anchor = (4063, "MidFirst")
    peers = [(110, "BOK")]
    facts = {
        (4063, "2025-Q4"): {"ASSET": Decimal("41200000")},
        (110, "2025-Q4"): {"ASSET": Decimal("48000000")},
    }
    sheets = build_comp_sheets(
        anchor=anchor,
        peers=peers,
        quarter_id="2025-Q4",
        income_statement_quarter_ids=["2025-Q4"],
        facts_by_cert_quarter=facts,
        ratios_by_cert={},
        ratio_defs=[],
    )
    bs = sheets[0].balance_sheet
    asset_line = next(line for line in bs if line.field_code == "ASSET")
    assert asset_line.anchor_value == Decimal("41200000")
    assert asset_line.peer_value == Decimal("48000000")


@dataclass
class _D:
    ratio_id: str
    display_name: str
    category: str
    numerator_formula: str
    denominator_formula: str


def _def(rid: str, category: str, name: str, num: str, den: str) -> _D:
    return _D(rid, name, category, num, den)
