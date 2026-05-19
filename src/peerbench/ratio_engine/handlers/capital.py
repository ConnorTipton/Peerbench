"""Capital ratios: tier1_lev, tier1_rbc, total_rbc, cet1.

tier1_rbc, total_rbc, and cet1 are pipeline-suppressed for CBLR filers
(CBLRIND=1) via suppress_when={"cblr": true} in ratio_defs. Handlers stay
pure — suppression is handled by the dispatcher before reaching them.

cet1 stays NotImplementedError until FFIEC CDR ingest lands (FDIC API
does not expose the CET1 capital dollar amount, only the ratio).
"""

from __future__ import annotations

from decimal import Decimal

from peerbench.ratio_engine.fact_view import FactView
from peerbench.ratio_engine.registry import ratio


@ratio("tier1_lev", version="v1")
def compute_tier1_lev(f: FactView) -> Decimal:
    # Tier 1 leverage = Tier 1 capital / adjusted average assets.
    # Same formula CBLR filers report as their CBLR ratio.
    return f["RBCT1J"] / f["AVASSETJ"]


@ratio("tier1_rbc", version="v1")
def compute_tier1_rbc(f: FactView) -> Decimal:
    # Tier 1 risk-based capital = Tier 1 capital / total RWA.
    # Suppressed for CBLR filers at pipeline layer (see ratio_defs.suppress_when).
    return f["RBCT1J"] / f["RWAJT"]


@ratio("total_rbc", version="v1")
def compute_total_rbc(f: FactView) -> Decimal:
    # Total RBC = (Tier 1 + Tier 2) / RWA. FDIC API doesn't expose a single
    # "total qualifying capital" $ field; compose from components.
    # Suppressed for CBLR filers.
    return (f["RBCT1J"] + f["RBCT2"]) / f["RWAJT"]


@ratio("cet1", version="v1")
def compute_cet1(f: FactView) -> Decimal:
    # FDIC API exposes the precomputed CET1 ratio (IDT1CER) but not the
    # CET1 dollar-amount numerator. FFIEC CDR Schedule RC-R Part I fills
    # the gap. Until then, this handler is intentionally unimplemented;
    # the dispatcher classifies the result as PartialResult.
    raise NotImplementedError("cet1 needs FFIEC CDR ingest (Day 3 plan-mode pause)")
