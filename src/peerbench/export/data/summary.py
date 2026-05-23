"""Build the Summary tab payload: anchor + peers × ratios, with median + rank + delta."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Protocol

from peerbench.export.data.types import SummaryRow, SummaryTab
from peerbench.export.directions import direction_for


class RatioDefLike(Protocol):
    ratio_id: str
    display_name: str
    category: str
    regulatory_threshold: dict[str, Any] | None


def compute_anchor_rank(
    *,
    anchor_value: Decimal | None,
    peer_values: list[Decimal | None],
    direction: str,
) -> int | None:
    """Direction-aware rank, 1 = best. Returns None for neutral or missing anchor."""
    if direction == "neutral" or anchor_value is None:
        return None
    all_values = [v for v in [anchor_value, *peer_values] if v is not None]
    if direction == "higher_is_positive":
        sorted_values = sorted(all_values, reverse=True)
    else:
        sorted_values = sorted(all_values)
    return sorted_values.index(anchor_value) + 1


def _median(values: list[Decimal]) -> Decimal | None:
    if not values:
        return None
    sorted_values = sorted(values)
    n = len(sorted_values)
    mid = n // 2
    if n % 2 == 1:
        return sorted_values[mid]
    return (sorted_values[mid - 1] + sorted_values[mid]) / 2


def build_summary(
    *,
    anchor: tuple[int, str],
    peers: list[tuple[int, str]],
    ratio_defs: list[RatioDefLike],
    ratios_by_cert: dict[int, dict[str, Decimal | None]],
    suppressed: set[tuple[int, str]],
) -> SummaryTab:
    rows: list[SummaryRow] = []
    anchor_cert = anchor[0]
    for r in ratio_defs:
        direction = direction_for(r.ratio_id)
        anchor_value = ratios_by_cert.get(anchor_cert, {}).get(r.ratio_id)
        if (anchor_cert, r.ratio_id) in suppressed:
            anchor_value = None

        peer_values_full: dict[int, Decimal | None] = {}
        peer_values_for_stats: list[Decimal] = []
        for cert, _name in peers:
            v = ratios_by_cert.get(cert, {}).get(r.ratio_id)
            if (cert, r.ratio_id) in suppressed:
                peer_values_full[cert] = None
            else:
                peer_values_full[cert] = v
                if v is not None:
                    peer_values_for_stats.append(v)

        peer_median = _median(peer_values_for_stats)
        peer_list_for_rank: list[Decimal | None] = [peer_values_full[c] for c, _ in peers]
        rank = compute_anchor_rank(
            anchor_value=anchor_value,
            peer_values=peer_list_for_rank,
            direction=direction,
        )
        delta = (
            anchor_value - peer_median
            if anchor_value is not None and peer_median is not None
            else None
        )

        threshold = r.regulatory_threshold or {}
        amber_pct_raw = threshold.get("amber_pct")
        red_pct_raw = threshold.get("red_pct")

        rows.append(
            SummaryRow(
                ratio_id=r.ratio_id,
                display_name=r.display_name,
                category=r.category,
                anchor_value=anchor_value,
                peer_values=peer_values_full,
                peer_median=peer_median,
                anchor_rank=rank,
                delta_vs_median=delta,
                direction=direction,
                amber_pct=Decimal(str(amber_pct_raw)) / 100 if amber_pct_raw is not None else None,
                red_pct=Decimal(str(red_pct_raw)) / 100 if red_pct_raw is not None else None,
            )
        )
    return SummaryTab(institution_columns=[anchor, *peers], rows=rows)
