"""Concentration ratios: cre_rbc, cd_rbc, top_loan_cat.

SR 07-1 / FIL-23-2023 thresholds on CRE concentration are surfaced in the
dashboard via ratio_defs.regulatory_threshold (300% amber, 100% for C&D).
"""

from __future__ import annotations

from decimal import Decimal

from peerbench.ratio_engine.fact_view import FactView
from peerbench.ratio_engine.registry import ratio


@ratio("cre_rbc", version="v1")
def compute_cre_rbc(f: FactView) -> Decimal:
    # CRE = construction + multifamily + nonfarm nonresidential.
    # Denominator = total risk-based capital (T1 + T2). SR 07-1 threshold.
    cre = f["LNRECONS"] + f["LNREMULT"] + f["LNRENRES"]
    return cre / (f["RBCT1J"] + f["RBCT2"])


@ratio("cd_rbc", version="v1")
def compute_cd_rbc(f: FactView) -> Decimal:
    # Construction & land development / total RBC. SR 07-1 100% threshold.
    return f["LNRECONS"] / (f["RBCT1J"] + f["RBCT2"])


@ratio("top_loan_cat", version="v1")
def compute_top_loan_cat(f: FactView) -> Decimal:
    # Single largest loan category as % of total loans. Day 3 only has 3 of
    # the ~10 RC-C subcategories ingested (LNRECONS, LNREMULT, LNRENRES);
    # banks dominated by C&I, 1-4 family, consumer, or ag would silently
    # report a wrong CRE subcategory as the "top". Surface as partial until
    # the full RC-C field set lands in src/peerbench/fdic_fields.py.
    raise NotImplementedError(
        "top_loan_cat needs full RC-C subcategory ingest (Day 4+ field expansion)"
    )
