"""The field codes the ingest pipeline writes to `facts.field_code`.

Single source of truth: any code referenced in a ratio handler must also
appear here, otherwise the ingest pipeline won't fetch it. Add codes here
when wiring a new handler.

Two sources feed `facts`:
  - FDIC BankFind API (METADATA / BALANCE_SHEET / INCOME / CAPITAL /
    PRECOMPUTED tuples) — codes match the FDIC field reference verbatim.
  - FFIEC CDR bulk files (CDR_FIELDS tuple) — codes use a `CDR_*` namespace
    prefix so they cannot collide with FDIC API codes when grepping the
    `facts` table. CDR ingest fills fields the FDIC API does not expose
    (e.g. CET1 capital dollar amount from RC-R Part I, HTM fair value
    from RC-B Memorandum 2).
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
    "ELNATR",  # Provision for credit losses — Phase 4.2 Comp Sheet I/S.
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

# FFIEC CDR fields — bulk-file sourced. Namespaced with `CDR_*` so they
# never collide with FDIC API codes in `facts.field_code`.
CDR_FIELDS: tuple[str, ...] = (
    "CDR_CET1_CAPITAL",  # RC-R Part I: CET1 capital dollar amount (numerator for `cet1`)
    "CDR_HTM_FAIRVAL",  # RC-B Memorandum 2: HTM fair value (paired with SCHA for `htm_loss_t1`)
)


def all_fields() -> tuple[str, ...]:
    """Field codes the FDIC BankFind API is asked to return per bank-quarter.

    Excludes `CDR_FIELDS` because those come from FFIEC CDR bulk files, not
    the API — passing them in an FDIC API request would be a wasted code.
    """
    return (
        METADATA_FIELDS
        + BALANCE_SHEET_FIELDS
        + INCOME_FIELDS
        + CAPITAL_FIELDS
        + PRECOMPUTED_RATIO_FIELDS
    )


def all_field_codes() -> tuple[str, ...]:
    """Every field code the pipeline can write to `facts.field_code`."""
    return all_fields() + CDR_FIELDS
