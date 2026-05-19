"""Capital ratios: tier1_lev, tier1_rbc, total_rbc, cet1.

tier1_rbc, total_rbc, and cet1 are suppressed at pipeline level for CBLR
filers (CBLRIND=1) via suppress_when={"cblr": true} in ratio_defs. The
handlers stay pure — suppression is handled in
peerbench.ratio_engine.suppression.should_suppress, called by the dispatcher
before reaching the handler.
"""

from __future__ import annotations

from decimal import Decimal

from peerbench.ratio_engine.fact_view import FactView
from peerbench.ratio_engine.registry import ratio


@ratio("tier1_lev", version="v1")
def compute_tier1_lev(f: FactView) -> Decimal:
    # Day 3: RBCT1J / AVASSETJ
    raise NotImplementedError("tier1_lev handler body lands Day 3")


@ratio("tier1_rbc", version="v1")
def compute_tier1_rbc(f: FactView) -> Decimal:
    # Day 3: RBCT1J / RWAJT (suppressed for CBLR filers at pipeline layer)
    raise NotImplementedError("tier1_rbc handler body lands Day 3")


@ratio("total_rbc", version="v1")
def compute_total_rbc(f: FactView) -> Decimal:
    # Day 3: (RBCT1J + RBCT2) / RWAJT (suppressed for CBLR)
    raise NotImplementedError("total_rbc handler body lands Day 3")


@ratio("cet1", version="v1")
def compute_cet1(f: FactView) -> Decimal:
    # Day 3: CET1 capital from FFIEC CDR RC-R Part I / RWAJT (suppressed for CBLR).
    # FDIC API does not expose CET1 dollar amount — CDR ingest fills the gap.
    raise NotImplementedError("cet1 handler body lands Day 3")
