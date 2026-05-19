"""Concentration ratios: cre_rbc, cd_rbc, top_loan_cat."""

from __future__ import annotations

from decimal import Decimal

from peerbench.ratio_engine.fact_view import FactView
from peerbench.ratio_engine.registry import ratio


@ratio("cre_rbc", version="v1")
def compute_cre_rbc(f: FactView) -> Decimal:
    # Day 3: (LNRECONS + LNREMULT + LNRENRES) / (RBCT1J + RBCT2)
    raise NotImplementedError("cre_rbc handler body lands Day 3")


@ratio("cd_rbc", version="v1")
def compute_cd_rbc(f: FactView) -> Decimal:
    # Day 3: LNRECONS / (RBCT1J + RBCT2)
    raise NotImplementedError("cd_rbc handler body lands Day 3")


@ratio("top_loan_cat", version="v1")
def compute_top_loan_cat(f: FactView) -> Decimal:
    # Day 3: MAX of RC-C subcategory balances / LNLSGR. Sidecar column for
    # the category name.
    raise NotImplementedError("top_loan_cat handler body lands Day 3")
