"""The FDIC field codes the ingest pipeline pulls per bank-quarter.

Single source of truth: any code referenced in a ratio handler (Day 3) must
also appear here, otherwise the FDIC API won't return it. Add codes here
when wiring a new handler.

These cover the 30 ratios in data/ratios.csv plus the precomputed-ratio
codes used for Day 4 validation. Two ratios (`cet1`, `htm_loss_t1`) need
fields the FDIC API does not expose (CET1 capital $, HTM fair value) — those
come from FFIEC CDR ingest, scaffolded in Day 3.
"""

from __future__ import annotations

# Institution metadata
METADATA_FIELDS: tuple[str, ...] = (
    "CERT",
    "NAMEFULL",
    "CITY",
    "STALP",
    "ACTIVE",
    "REPDTE",
    "RSSDID",
    "CBLRIND",
)

# Balance sheet
BALANCE_SHEET_FIELDS: tuple[str, ...] = (
    "ASSET",
    "ASSET5",
    "AVASSETJ",
    "DEP",
    "DEPI",
    "DEPUNA",
    "DEPINS",
    "BRO",
    "LIAB",
    "EQ",
    "EQ5",
    "LNLSGR",
    "LNLSGR5",
    "LNLSNET",
    "LNATRES",
    "NCLNLS",
    "SC",
    "SCHA",
    "CHBAL",
    "CHBALI",
    "CHBALNI",
    "INTAN",
    "INTANGW",
    "INTANMSR",
    "INTANOTH",
    "LNRECONS",
    "LNREMULT",
    "LNRENRES",
)

# Income statement
INCOME_FIELDS: tuple[str, ...] = (
    "NETINC",
    "NIM",
    "INTINC",
    "EINTEXP",
    "ERNAST",
    "ERNAST5",
    "NONII",
    "NONIX",
    "NTLNLS",
    "EAMINTAN",
)

# Risk-based capital
CAPITAL_FIELDS: tuple[str, ...] = (
    "RBCT1J",
    "RBCT2",
    "RWAJT",
)

# FDIC precomputed ratios for Day 4 validation
PRECOMPUTED_RATIO_FIELDS: tuple[str, ...] = (
    "NIMY",
    "ROA",
    "ROE",
    "EEFFR",
    "INTINCY",
    "LNLSDEPR",
    "LNATRESR",
    "NTLNLSR",
    "LNRESNCR",
    "NCLNLSR",
    "RBC1AAJ",
    "IDT1RWAJR",
    "RBCRWAJ",
    "IDT1CER",
)


def all_fields() -> tuple[str, ...]:
    return (
        METADATA_FIELDS
        + BALANCE_SHEET_FIELDS
        + INCOME_FIELDS
        + CAPITAL_FIELDS
        + PRECOMPUTED_RATIO_FIELDS
    )
