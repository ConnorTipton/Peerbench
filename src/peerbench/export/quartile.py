from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

Direction = Literal["higher_is_positive", "higher_is_negative", "neutral"]
Bucket = Literal["top", "middle", "bottom", "none"]

MIN_VALUES_FOR_QUARTILES = 4


@dataclass(frozen=True, slots=True)
class QuartileCutoffs:
    q1: Decimal
    median: Decimal
    q3: Decimal


def compute_quartile_cutoffs(
    values: list[Decimal | None],
) -> QuartileCutoffs | None:
    """Type-7 quantile cutoffs over non-None values. Mirrors web/lib/heatmap.ts."""
    filtered = [v for v in values if v is not None]
    if len(filtered) < MIN_VALUES_FOR_QUARTILES:
        return None
    sorted_values = sorted(filtered)
    return QuartileCutoffs(
        q1=_quantile(sorted_values, Decimal("0.25")),
        median=_quantile(sorted_values, Decimal("0.5")),
        q3=_quantile(sorted_values, Decimal("0.75")),
    )


def _quantile(sorted_values: list[Decimal], q: Decimal) -> Decimal:
    n = len(sorted_values)
    idx = (Decimal(n) - 1) * q
    lo = int(idx)
    frac = idx - Decimal(lo)
    if frac == 0:
        return sorted_values[lo]
    return sorted_values[lo] + (sorted_values[lo + 1] - sorted_values[lo]) * frac


def bucket_for_cell(
    value: Decimal | None,
    cutoffs: QuartileCutoffs | None,
    direction: Direction,
) -> Bucket:
    """Direction-aware top/middle/bottom/none. `top` = green tint, `bottom` = red tint."""
    if value is None or cutoffs is None or direction == "neutral":
        return "none"
    if value > cutoffs.q3:
        return "top" if direction == "higher_is_positive" else "bottom"
    if value < cutoffs.q1:
        return "bottom" if direction == "higher_is_positive" else "top"
    return "middle"
