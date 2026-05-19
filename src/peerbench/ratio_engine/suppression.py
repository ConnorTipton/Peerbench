"""Pipeline-level ratio suppression — keeps handlers pure.

Handlers compute facts → Decimal and nothing else. Suppression (CBLR for
capital ratios, missing-field 'partial' marking) lives here, evaluated
*before* dispatching to the handler.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from peerbench.db.models import RatioDef
from peerbench.ratio_engine.fact_view import FactView


@dataclass(frozen=True)
class SuppressedResult:
    reason: str  # 'cblr', 'missing_field', ...


@dataclass(frozen=True)
class PartialResult:
    value: Decimal | None
    missing_fields: tuple[str, ...]


def should_suppress(ratio_def: RatioDef, fact_view: FactView) -> SuppressedResult | None:
    """Return a SuppressedResult if the ratio should be skipped for this bank-quarter."""
    suppress = ratio_def.suppress_when or {}
    if suppress.get("cblr"):
        cblr_ind = fact_view.current.get("CBLRIND")
        if cblr_ind is not None and cblr_ind == Decimal(1):
            return SuppressedResult(reason="cblr")
    return None
