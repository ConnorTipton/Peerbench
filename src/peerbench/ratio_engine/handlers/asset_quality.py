"""Asset quality ratios: npl_ratio, nco_ratio, acl_loans, acl_npl."""

from __future__ import annotations

from decimal import Decimal

from peerbench.ratio_engine.fact_view import FactView
from peerbench.ratio_engine.registry import ratio


@ratio("npl_ratio", version="v1")
def compute_npl_ratio(f: FactView) -> Decimal:
    # Day 3: NCLNLS / LNLSGR
    raise NotImplementedError("npl_ratio handler body lands Day 3")


@ratio("nco_ratio", version="v1")
def compute_nco_ratio(f: FactView) -> Decimal:
    # Day 3: NTLNLS × annualize_factor / LNLSGR5
    raise NotImplementedError("nco_ratio handler body lands Day 3")


@ratio("acl_loans", version="v1")
def compute_acl_loans(f: FactView) -> Decimal:
    # Day 3: LNATRES / LNLSGR
    raise NotImplementedError("acl_loans handler body lands Day 3")


@ratio("acl_npl", version="v1")
def compute_acl_npl(f: FactView) -> Decimal:
    # Day 3: LNATRES / NCLNLS
    raise NotImplementedError("acl_npl handler body lands Day 3")
