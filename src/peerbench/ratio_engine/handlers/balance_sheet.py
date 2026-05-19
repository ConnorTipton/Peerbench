"""Balance-sheet mix ratios: loans_deposits, loans_assets, sec_assets,
cash_assets, deposits_liab, nonint_inc_rev, nonint_exp_assets, tce_ta.
"""

from __future__ import annotations

from decimal import Decimal

from peerbench.ratio_engine.fact_view import FactView
from peerbench.ratio_engine.registry import ratio


@ratio("loans_deposits", version="v1")
def compute_loans_deposits(f: FactView) -> Decimal:
    # Day 3: LNLSGR / DEP. FDIC LNLSDEPR uses NET loans — gap documented.
    raise NotImplementedError("loans_deposits handler body lands Day 3")


@ratio("loans_assets", version="v1")
def compute_loans_assets(f: FactView) -> Decimal:
    # Day 3: LNLSGR / ASSET
    raise NotImplementedError("loans_assets handler body lands Day 3")


@ratio("sec_assets", version="v1")
def compute_sec_assets(f: FactView) -> Decimal:
    # Day 3: SC / ASSET
    raise NotImplementedError("sec_assets handler body lands Day 3")


@ratio("cash_assets", version="v1")
def compute_cash_assets(f: FactView) -> Decimal:
    # Day 3: CHBAL / ASSET
    raise NotImplementedError("cash_assets handler body lands Day 3")


@ratio("deposits_liab", version="v1")
def compute_deposits_liab(f: FactView) -> Decimal:
    # Day 3: DEP / LIAB
    raise NotImplementedError("deposits_liab handler body lands Day 3")


@ratio("nonint_inc_rev", version="v1")
def compute_nonint_inc_rev(f: FactView) -> Decimal:
    # Day 3: NONII / (NIM + NONII)
    raise NotImplementedError("nonint_inc_rev handler body lands Day 3")


@ratio("nonint_exp_assets", version="v1")
def compute_nonint_exp_assets(f: FactView) -> Decimal:
    # Day 3: NONIX × annualize_factor / ASSET5
    raise NotImplementedError("nonint_exp_assets handler body lands Day 3")


@ratio("tce_ta", version="v1")
def compute_tce_ta(f: FactView) -> Decimal:
    # Day 3: (EQ - INTAN) / (ASSET - INTAN)
    raise NotImplementedError("tce_ta handler body lands Day 3")
