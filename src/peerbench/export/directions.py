"""Per-ratio heat-map direction lookup. Mirrors web/lib/heatmap-directions.ts; contract test enforces 1:1 correspondence."""

from __future__ import annotations

from typing import Literal

Direction = Literal["higher_is_positive", "higher_is_negative", "neutral"]

RATIO_DIRECTIONS: dict[str, Direction] = {
    # Profitability.
    "nim": "higher_is_positive",
    "roa": "higher_is_positive",
    "roe": "higher_is_positive",
    "eff_ratio": "higher_is_negative",
    "ppnr_assets": "higher_is_positive",
    # Yields & costs.
    "yield_ea": "higher_is_positive",
    "cost_funds": "higher_is_negative",
    "nis": "higher_is_positive",
    # Balance sheet mix.
    "loans_deposits": "neutral",
    "loans_assets": "neutral",
    "sec_assets": "neutral",
    "cash_assets": "neutral",
    "deposits_liab": "neutral",
    "nonint_inc_rev": "higher_is_positive",
    "nonint_exp_assets": "higher_is_negative",
    "tce_ta": "higher_is_positive",
    # Asset quality.
    "npl_ratio": "higher_is_negative",
    "nco_ratio": "higher_is_negative",
    "acl_loans": "neutral",
    "acl_npl": "higher_is_positive",
    # Capital.
    "tier1_lev": "higher_is_positive",
    "tier1_rbc": "higher_is_positive",
    "total_rbc": "higher_is_positive",
    "cet1": "higher_is_positive",
    # Concentration.
    "cre_rbc": "neutral",
    "cd_rbc": "neutral",
    "top_loan_cat": "higher_is_negative",
    # Liquidity & deposit composition.
    "uninsured_dep": "higher_is_negative",
    "brokered_dep": "higher_is_negative",
    "htm_loss_t1": "higher_is_negative",
}


def direction_for(ratio_id: str) -> Direction:
    return RATIO_DIRECTIONS.get(ratio_id, "neutral")
