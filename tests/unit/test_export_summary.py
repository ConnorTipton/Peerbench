from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from peerbench.export.data.summary import (
    build_summary,
    compute_anchor_rank,
)


def test_compute_anchor_rank_higher_is_positive() -> None:
    rank = compute_anchor_rank(
        anchor_value=Decimal(50),
        peer_values=[Decimal(10), Decimal(20), Decimal(30), Decimal(40)],
        direction="higher_is_positive",
    )
    assert rank == 1


def test_compute_anchor_rank_higher_is_negative_inverts() -> None:
    rank = compute_anchor_rank(
        anchor_value=Decimal(50),
        peer_values=[Decimal(10), Decimal(20), Decimal(30), Decimal(40)],
        direction="higher_is_negative",
    )
    assert rank == 5


def test_compute_anchor_rank_neutral_returns_none() -> None:
    rank = compute_anchor_rank(
        anchor_value=Decimal(50),
        peer_values=[Decimal(10), Decimal(20), Decimal(30), Decimal(40)],
        direction="neutral",
    )
    assert rank is None


def test_compute_anchor_rank_anchor_none_returns_none() -> None:
    rank = compute_anchor_rank(
        anchor_value=None,
        peer_values=[Decimal(10), Decimal(20)],
        direction="higher_is_positive",
    )
    assert rank is None


def test_compute_anchor_rank_drops_none_peers() -> None:
    rank = compute_anchor_rank(
        anchor_value=Decimal(35),
        peer_values=[Decimal(10), None, Decimal(20), Decimal(40)],
        direction="higher_is_positive",
    )
    assert rank == 2


def test_build_summary_rows_anchor_first_in_columns() -> None:
    anchor = (4063, "MidFirst")
    peers = [(110, "BOK"), (4214, "Comerica")]
    ratio_defs = [_def("nim", "profitability", "Net Interest Margin")]
    ratios_by_cert = {
        4063: {"nim": Decimal("0.035")},
        110: {"nim": Decimal("0.030")},
        4214: {"nim": Decimal("0.028")},
    }
    tab = build_summary(
        anchor=anchor,
        peers=peers,
        ratio_defs=ratio_defs,
        ratios_by_cert=ratios_by_cert,
        suppressed=set(),
    )
    assert tab.institution_columns[0] == anchor
    assert tab.institution_columns[1:] == peers
    assert tab.rows[0].anchor_value == Decimal("0.035")
    assert tab.rows[0].peer_values[110] == Decimal("0.030")


def test_build_summary_excludes_suppressed_from_median() -> None:
    anchor = (4063, "MidFirst")
    peers = [(110, "BOK"), (4214, "Comerica"), (5510, "Frost")]
    ratio_defs = [_def("tier1_rbc", "capital", "Tier 1 RBC")]
    ratios_by_cert = {
        4063: {"tier1_rbc": Decimal("0.11")},
        110: {"tier1_rbc": Decimal("0.12")},
        4214: {"tier1_rbc": None},
        5510: {"tier1_rbc": Decimal("0.13")},
    }
    suppressed = {(4214, "tier1_rbc")}
    tab = build_summary(
        anchor=anchor,
        peers=peers,
        ratio_defs=ratio_defs,
        ratios_by_cert=ratios_by_cert,
        suppressed=suppressed,
    )
    assert tab.rows[0].peer_median == Decimal("0.125")


def test_build_summary_neutral_direction_skips_rank() -> None:
    anchor = (4063, "MidFirst")
    peers = [(110, "BOK"), (4214, "Comerica"), (5510, "Frost"), (11063, "BankX")]
    ratio_defs = [_def("loans_assets", "balance_sheet", "Loans / Assets")]
    ratios_by_cert = {
        4063: {"loans_assets": Decimal("0.6")},
        110: {"loans_assets": Decimal("0.5")},
        4214: {"loans_assets": Decimal("0.7")},
        5510: {"loans_assets": Decimal("0.55")},
        11063: {"loans_assets": Decimal("0.65")},
    }
    tab = build_summary(
        anchor=anchor,
        peers=peers,
        ratio_defs=ratio_defs,
        ratios_by_cert=ratios_by_cert,
        suppressed=set(),
    )
    assert tab.rows[0].anchor_rank is None


@dataclass
class _D:
    ratio_id: str
    display_name: str
    category: str
    regulatory_threshold: dict | None = None


def _def(rid: str, category: str, name: str) -> _D:
    return _D(rid, name, category)
