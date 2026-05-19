"""Importing this package registers every handler with the registry.

Each module below decorates its handlers with @ratio(...). Importing them
all in __init__ guarantees the registry is fully populated by the time any
caller asks `registered_handlers()`.
"""

from peerbench.ratio_engine.handlers import (
    asset_quality,
    balance_sheet,
    capital,
    concentration,
    liquidity,
    profitability,
    yields,
)

__all__ = [
    "asset_quality",
    "balance_sheet",
    "capital",
    "concentration",
    "liquidity",
    "profitability",
    "yields",
]
