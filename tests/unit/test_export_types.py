from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from peerbench.export.data.types import (
    CoverTab,
    SummaryRow,
    SummaryTab,
    WorkbookBundle,
)


def test_workbook_bundle_construction() -> None:
    cover = CoverTab(
        anchor_cert=4063,
        anchor_name="MidFirst",
        quarter_id="2025-Q4",
        quarter_end="December 31, 2025",
        generated_at=datetime(2026, 5, 23, 12, 0, 0),
        data_vintage="2026-05-22",
        notes=[],
    )
    summary = SummaryTab(
        institution_columns=[(4063, "MidFirst")],
        rows=[
            SummaryRow(
                ratio_id="nim",
                display_name="Net Interest Margin",
                category="profitability",
                anchor_value=Decimal("0.034"),
                peer_values={},
                peer_median=None,
                anchor_rank=1,
                delta_vs_median=None,
                direction="higher_is_positive",
                amber_pct=None,
                red_pct=None,
            )
        ],
    )
    bundle = WorkbookBundle(
        cover=cover,
        summary=summary,
        comp_sheets=[],
        time_series=[],
        restatement_log=None,
        methodology=None,
    )
    assert bundle.cover.anchor_cert == 4063
    assert bundle.summary.rows[0].ratio_id == "nim"
