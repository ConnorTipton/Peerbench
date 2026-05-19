"""Asset quality ratios: npl_ratio, nco_ratio, acl_loans, acl_npl.

Post-CECL nomenclature: ACL (allowance for credit losses), not ALLL.
NCLNLS = noncurrent loans (nonaccrual + 90+ DPD still accruing).
"""

from __future__ import annotations

from decimal import Decimal

from peerbench.ratio_engine.fact_view import FactView
from peerbench.ratio_engine.registry import ratio


@ratio("npl_ratio", version="v1")
def compute_npl_ratio(f: FactView) -> Decimal:
    # NPL = noncurrent loans / total gross loans. FDIC precomputed
    # LNRESNCR likely uses the same denominator — verify in Day 4.
    return f["NCLNLS"] / f["LNLSGR"]


@ratio("nco_ratio", version="v1")
def compute_nco_ratio(f: FactView) -> Decimal:
    # Net charge-off ratio (annualized). NTLNLS is YTD $ charge-offs;
    # denominator is YTD average loans, FDIC convention = prior year-end +
    # current YTD quarter-ends (quarter_number + 1 observations: 2/3/4/5
    # for Q1/Q2/Q3/Q4). Hardcoding 5 would only match Q4.
    return f["NTLNLS"] * f.annualize_factor() / f.avg("LNLSGR", periods=f.quarter_number + 1)


@ratio("acl_loans", version="v1")
def compute_acl_loans(f: FactView) -> Decimal:
    return f["LNATRES"] / f["LNLSGR"]


@ratio("acl_npl", version="v1")
def compute_acl_npl(f: FactView) -> Decimal:
    # Coverage ratio: ACL / non-performing loans. Banks with no NPLs would
    # divide by zero; that surfaces as PartialResult upstream.
    return f["LNATRES"] / f["NCLNLS"]
