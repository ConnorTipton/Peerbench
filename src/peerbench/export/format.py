from __future__ import annotations

from decimal import Decimal

EM_DASH = "—"


def format_ratio_for_cell(value: Decimal | None) -> float | None:
    """Stored ratio (fraction) → float for openpyxl; cell number_format renders percent + parens."""
    if value is None:
        return None
    return float(value)


def format_fact_value(value: Decimal | None) -> str:
    """Call Report dollar value (thousands) → grouped integer string; negatives in parens; None → em-dash."""
    if value is None:
        return EM_DASH
    if value < 0:
        return f"({format(abs(value), ',.0f')})"
    return format(value, ",.0f")


def format_delta_bps(anchor: Decimal | None, peer: Decimal | None) -> str:
    """Anchor − peer as a basis-point delta string. Inputs are fractions."""
    if anchor is None or peer is None:
        return EM_DASH
    delta = anchor - peer
    bps = int((delta * Decimal(10000)).quantize(Decimal("1")))
    if bps < 0:
        return f"({abs(bps)} bps)"
    return f"+{bps} bps"
