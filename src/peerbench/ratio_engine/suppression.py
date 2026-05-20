"""Pipeline-level ratio suppression — keeps handlers pure.

Handlers compute facts → Decimal and nothing else. Suppression (CBLR for
capital ratios, missing-field 'partial' marking) lives here, evaluated
*before* dispatching to the handler.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

from peerbench.db.models import RatioDef
from peerbench.ratio_engine.fact_view import FactView

# Field codes consulted per `ratio_defs.suppress_when` key. Single source of
# truth for the dependency graph: `should_suppress` reads these fields, so a
# restatement to one must invalidate any ratio that opts into the matching
# suppression key. Mirrored by `ratio_engine.field_deps` so the restatement
# detector and dashboard marker see suppression edges that handler ASTs alone
# don't expose. When you add a new suppression branch below, add its field
# codes here too.
SUPPRESS_KEY_FIELDS: Mapping[str, tuple[str, ...]] = {
    "cblr": ("CBLRIND",),
}


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
