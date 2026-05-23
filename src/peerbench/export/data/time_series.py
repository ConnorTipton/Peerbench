"""Build Time Series tab payloads — one tab per category, stacked blocks per ratio."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Protocol

from peerbench.export.data.comp_sheet import sanitize_sheet_name
from peerbench.export.data.types import TimeSeriesBlock, TimeSeriesTab
from peerbench.export.directions import direction_for

CATEGORY_LABELS = {
    "profitability": "Profitability",
    "yields": "Yields & costs",
    "balance_sheet": "Balance sheet mix",
    "asset_quality": "Asset quality",
    "capital": "Capital",
    "concentration": "Concentration",
    "liquidity": "Liquidity & deposit composition",
}

CATEGORY_ORDER = (
    "profitability",
    "yields",
    "balance_sheet",
    "asset_quality",
    "capital",
    "concentration",
    "liquidity",
)


class RatioDefLike(Protocol):
    ratio_id: str
    display_name: str
    category: str
    numerator_formula: str
    denominator_formula: str


def build_time_series(
    *,
    anchor: tuple[int, str],
    peers: list[tuple[int, str]],
    quarter_ids: list[str],
    ratios_by_cert_quarter: dict[int, dict[tuple[str, str], Decimal | None]],
    ratio_defs: list[RatioDefLike],
) -> list[TimeSeriesTab]:
    by_category: dict[str, list[RatioDefLike]] = defaultdict(list)
    for r in ratio_defs:
        by_category[r.category].append(r)

    institutions = [anchor, *peers]
    used_names: set[str] = set()
    tabs: list[TimeSeriesTab] = []
    for category in CATEGORY_ORDER:
        ratios_in_cat = by_category.get(category)
        if not ratios_in_cat:
            continue
        blocks: list[TimeSeriesBlock] = []
        for r in ratios_in_cat:
            rows: list[tuple[int, str, list[Decimal | None]]] = []
            for cert, name in institutions:
                vals = [
                    ratios_by_cert_quarter.get(cert, {}).get((q, r.ratio_id)) for q in quarter_ids
                ]
                rows.append((cert, name, vals))
            blocks.append(
                TimeSeriesBlock(
                    ratio_id=r.ratio_id,
                    display_name=r.display_name,
                    formula=f"{r.numerator_formula} / {r.denominator_formula}",
                    direction=direction_for(r.ratio_id),
                    quarter_ids=list(quarter_ids),
                    rows=rows,
                )
            )
        sheet_name = sanitize_sheet_name(CATEGORY_LABELS[category], used=used_names)
        used_names.add(sheet_name)
        tabs.append(
            TimeSeriesTab(
                sheet_name=sheet_name,
                category=category,
                category_label=CATEGORY_LABELS[category],
                blocks=blocks,
            )
        )
    return tabs
