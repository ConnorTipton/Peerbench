"""Balance-sheet mix ratios. Mostly EOP — period-end balances divided by
each other. Two are annualized YTD-flow ratios (nonint_inc_rev uses YTD
income components; nonint_exp_assets is a YTD expense over avg assets).
"""

from __future__ import annotations

from decimal import Decimal

from peerbench.ratio_engine.fact_view import FactView
from peerbench.ratio_engine.registry import ratio


@ratio("loans_deposits", version="v1")
def compute_loans_deposits(f: FactView) -> Decimal:
    # Gross loans / total deposits. FDIC's precomputed LNLSDEPR uses NET
    # loans (LNLSGR - LNATRES - LNCONTRA); expect ~1-2% gap.
    return f["LNLSGR"] / f["DEP"]


@ratio("loans_assets", version="v1")
def compute_loans_assets(f: FactView) -> Decimal:
    return f["LNLSGR"] / f["ASSET"]


@ratio("sec_assets", version="v1")
def compute_sec_assets(f: FactView) -> Decimal:
    return f["SC"] / f["ASSET"]


@ratio("cash_assets", version="v1")
def compute_cash_assets(f: FactView) -> Decimal:
    return f["CHBAL"] / f["ASSET"]


@ratio("deposits_liab", version="v1")
def compute_deposits_liab(f: FactView) -> Decimal:
    return f["DEP"] / f["LIAB"]


@ratio("nonint_inc_rev", version="v1")
def compute_nonint_inc_rev(f: FactView) -> Decimal:
    # Revenue mix indicator. NIM and NONII are both YTD, so no annualize
    # factor — the ratio is unitless.
    return f["NONII"] / (f["NIM"] + f["NONII"])


@ratio("nonint_exp_assets", version="v1")
def compute_nonint_exp_assets(f: FactView) -> Decimal:
    # Operating cost burden, annualized.
    return f["NONIX"] * f.annualize_factor() / f["ASSET5"]


@ratio("tce_ta", version="v1")
def compute_tce_ta(f: FactView) -> Decimal:
    # Tangible common equity / tangible assets. Strip the full INTAN stack
    # (goodwill + MSR + other intangibles) from both sides. Banks with no
    # intangibles return NULL for INTAN; treat as zero.
    intan = f.get("INTAN", default=Decimal(0))
    return (f["EQ"] - intan) / (f["ASSET"] - intan)
