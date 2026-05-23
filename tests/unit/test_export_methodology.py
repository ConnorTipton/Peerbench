from __future__ import annotations

from peerbench.db import RatioDef
from peerbench.export.data.methodology import (
    build_methodology,
    render_regulatory_threshold,
)


def test_render_regulatory_threshold_amber_red() -> None:
    payload = {"amber_pct": 300, "red_pct": 400, "citation": "SR 07-1 §III.A"}
    rendered = render_regulatory_threshold(payload)
    assert rendered is not None
    assert "300" in rendered
    assert "400" in rendered
    assert "SR 07-1 §III.A" in rendered


def test_render_regulatory_threshold_none() -> None:
    assert render_regulatory_threshold(None) is None


def test_render_regulatory_threshold_amber_only() -> None:
    rendered = render_regulatory_threshold({"amber_pct": 100, "citation": "OCC Bulletin 2006-46"})
    assert rendered is not None
    assert "100" in rendered
    assert "OCC Bulletin 2006-46" in rendered


def test_build_methodology_emits_block_per_ratio_def() -> None:
    defs = [
        RatioDef(
            ratio_id="nim",
            display_name="Net Interest Margin",
            category="profitability",
            numerator_formula="Net interest income",
            denominator_formula="Average earning assets",
            annualize=True,
            avg_or_eop="AVG",
            fdic_precomputed_code="NIMY",
            ubpr_concept="UBPR3404",
            regulatory_threshold=None,
            suppress_when=None,
            notes="Non-tax-equivalent.",
        ),
        RatioDef(
            ratio_id="cre_rbc",
            display_name="CRE / Total RBC",
            category="concentration",
            numerator_formula="CRE loans",
            denominator_formula="Total RBC",
            annualize=False,
            avg_or_eop="EOP",
            fdic_precomputed_code=None,
            ubpr_concept=None,
            regulatory_threshold={
                "amber_pct": 300,
                "red_pct": 400,
                "citation": "SR 07-1 §III.A",
            },
            suppress_when=None,
            notes=None,
        ),
    ]
    field_deps = {
        "nim": ["INTINC", "EINTEXP", "ERNAST5"],
        "cre_rbc": ["LNRECONS", "LNREMULT", "LNRENRES", "RBCT1J", "RBCT2"],
    }
    tab = build_methodology(defs, field_deps=field_deps)
    assert len(tab.blocks) == 2
    nim_block = tab.blocks[0]
    assert nim_block.ratio_id == "nim"
    assert "Net interest income" in nim_block.formula
    assert nim_block.annualization == "YTD × 4/Qn"
    assert nim_block.basis == "AVG"
    assert nim_block.fdic_precomputed == "NIMY"
    assert nim_block.regulatory_threshold is None
    assert "INTINC" in nim_block.source_fields
    cre_block = tab.blocks[1]
    assert cre_block.regulatory_threshold is not None
    assert "300" in cre_block.regulatory_threshold


def test_build_methodology_intro_notes_present() -> None:
    tab = build_methodology([], field_deps={})
    assert len(tab.intro_notes) >= 5
