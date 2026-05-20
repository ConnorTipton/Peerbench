"""Liquidity / deposit composition: uninsured_dep, brokered_dep, htm_loss_t1.

uninsured_dep and brokered_dep are FDIC-API-only. htm_loss_t1 combines
HTM amortized cost (SCHA, FDIC API) with HTM fair value (FFIEC CDR
Schedule RC-B Memorandum 2, ingested via `peerbench ingest-cdr`).
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
    # Unrealized HTM loss / Tier 1 capital. SCHA = HTM amortized cost
    # (FDIC API); CDR_HTM_FAIRVAL = HTM fair value (FFIEC CDR RC-B Memo 2).
    # data/ratios.csv specifies "Floor at 0 (losses only, not gains)" — in a
    # falling-rate environment fair value can exceed book and a negative
    # ratio would invert risk ranking.
    unrealized_loss = max(Decimal(0), f["SCHA"] - f["CDR_HTM_FAIRVAL"])
    return unrealized_loss / f["RBCT1J"]
