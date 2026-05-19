"""Liquidity / deposit composition: uninsured_dep, brokered_dep, htm_loss_t1.

uninsured_dep and brokered_dep are FDIC-API-only. htm_loss_t1 needs FFIEC
CDR Schedule RC-B Memorandum 2 (HTM fair value not exposed by the API).
"""

from __future__ import annotations

from decimal import Decimal

from peerbench.ratio_engine.fact_view import FactView
from peerbench.ratio_engine.registry import ratio


@ratio("uninsured_dep", version="v1")
def compute_uninsured_dep(f: FactView) -> Decimal:
    # DEPUNA is self-reported by banks with ≥$1B in total assets; smaller
    # banks will surface MissingFieldError -> PartialResult. Optional fallback
    # computation DEP - DEPINS is a Day 4 refinement.
    return f["DEPUNA"] / f["DEP"]


@ratio("brokered_dep", version="v1")
def compute_brokered_dep(f: FactView) -> Decimal:
    return f["BRO"] / f["DEP"]


@ratio("htm_loss_t1", version="v1")
def compute_htm_loss_t1(f: FactView) -> Decimal:
    # FDIC API exposes HTM amortized cost (SCHA) but not HTM fair value.
    # The unrealized-loss numerator needs FFIEC CDR RC-B Memorandum 2.
    # Handler stays unimplemented until that ingest lands.
    raise NotImplementedError("htm_loss_t1 needs FFIEC CDR ingest (Day 3 plan-mode pause)")
