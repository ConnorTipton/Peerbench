"""Liquidity / deposit composition: uninsured_dep, brokered_dep, htm_loss_t1."""

from __future__ import annotations

from decimal import Decimal

from peerbench.ratio_engine.fact_view import FactView
from peerbench.ratio_engine.registry import ratio


@ratio("uninsured_dep", version="v1")
def compute_uninsured_dep(f: FactView) -> Decimal:
    # Day 3: DEPUNA / DEP (or fallback DEP - DEPINS / DEP for small peers).
    raise NotImplementedError("uninsured_dep handler body lands Day 3")


@ratio("brokered_dep", version="v1")
def compute_brokered_dep(f: FactView) -> Decimal:
    # Day 3: BRO / DEP
    raise NotImplementedError("brokered_dep handler body lands Day 3")


@ratio("htm_loss_t1", version="v1")
def compute_htm_loss_t1(f: FactView) -> Decimal:
    # Day 3: max(0, SCHA - HTM_FV) / RBCT1J. HTM fair value comes from
    # FFIEC CDR RC-B Memorandum 2 — not in FDIC API.
    raise NotImplementedError("htm_loss_t1 handler body lands Day 3")
