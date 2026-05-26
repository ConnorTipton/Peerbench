"""Per-quarter MDRM candidate lookup for FFIEC CDR schedule TSVs.

CDR schedule TSVs do not have stable column names across quarters — RC-R
was restructured for the CECL transition (March 2019), and FFIEC
periodically renumbers MDRM codes. A column can also appear under
multiple domain prefixes within a single quarter: domestic-only filers
use `RCOA*` for RC-R amounts, while filers with foreign offices use
`RCFA*`. To support both populations cleanly, this module returns a
tuple of candidate MDRMs per (quarter, field) — the caller picks the
first non-empty value per row.

Usage
-----
    >>> from peerbench.ingest.cdr_schema import cdr_columns, SCHEDULE_PATTERN
    >>> cdr_columns("2025-Q4", "CET1_CAPITAL")
    ('RCOAP859', 'RCFAP859')
    >>> SCHEDULE_PATTERN["CET1_CAPITAL"]
    'RCRI'

Stable field labels (`CET1_CAPITAL`, `RI_NET_INC`, `RC_TOTAL_ASSETS`, …)
are the pipeline's internal identifiers. The TSV column is the per-quarter
MDRM code that appears in the bulk file header. `SCHEDULE_PATTERN` maps
each label to the substring used to locate the right schedule file inside
the ZIP.

Schedule conventions
--------------------
- Schedule **RI** (income statement) uses `RIAD*` MDRMs, no domain split —
  income is reported once at consolidated level.
- Schedule **RC** (balance sheet) uses `RCFD*` (consolidated) / `RCON*`
  (domestic only) pairs for most line items.
- Schedule **RC-B** (securities) follows the same RCFD/RCON pair convention.
- **Deposit line items** (`RCFN*` / `RCON*`) are an exception: foreign-office
  filers report under `RCFN*` while domestic-only filers report under
  `RCON*`. The pair is reversed from RCFD/RCON but the pick-first-non-empty
  helper is domain-agnostic and still works.

Scope (PR 1 — Phase 5.1 expansion)
----------------------------------
Covers 24 quarters (2020-Q1 through 2025-Q4) to support the historical
backfill window. Older quarters raise KeyError with a diagnostic message.
MDRM stability has been empirically verified against the 2025-Q4 cached
ZIP for every line; CECL-era nomenclature shifts that affect pre-2020-Q2
quarters are noted on the individual entries and routed through
`_OVERRIDES` as needed.

Empirical pinning (2026-05-20, HTM fix 2026-05-25, Phase 5.1 expansion 2026-05-26)
---------------------------------------------------------------------------------
`P859` (CET1 capital amount) verified against Bank OZK (cert 110) live
CDR ZIPs: `RCOAP859 / RWAJT = 11.7244%` matches FDIC `IDT1CER` exactly.
Pre-CECL `RCOA8274` (Tier 1 capital amount) over-stated by 77 bps for
banks with AT1 preferred stock (CET1 < Tier 1).

`HTM_FAIRVAL` was originally mapped to MDRM `1773`, but Schedule RC-B
labels `1773` as "AVAILABLE-FOR-SALE SECURITIES" — i.e. AFS carrying
value, not HTM. The correct HTM fair value MDRM is `1771` (Schedule
RC-B label "TOTL SECS-HELD-TO-MATRTY-FAIR VALUE"). The mistake floored
`htm_loss_t1` to 0% for every bank because `SCHA (~$0.1–10B HTM book) -
RCON1773 (~$5–30B AFS book)` was always negative, then floored. Verified
2026-05-25 against First-Citizens (cert 11063) 2025-Q4: RCFD1771 =
$8.488B HTM fair value vs SCHA $9.645B amortized cost → real $1.157B
unrealized loss, ~5–6% of Tier 1.

Phase 5.1 expansion (2026-05-26): added ~45 Schedule RI / RC line items
to support the `/statements` view. All MDRMs cross-checked against the
2025-Q4 ZIP header. Income statement uses `RIAD*` (single domain), balance
sheet uses `RCFD*`/`RCON*` pairs, deposits use `RCON*`/`RCFN*` pairs.
"""

from __future__ import annotations

# Field label → substring used to locate the right schedule file(s) inside
# the Subject Data Format ZIP. FFIEC names schedule files like
# `FFIEC CDR Call Schedule RCRI 12312025.txt` (single-file) or
# `FFIEC CDR Call Schedule RCB 12312025(1 of 2).txt` (split). The 4-letter
# token is the discriminator; multi-file fan-in is handled in cdr.py.
SCHEDULE_PATTERN: dict[str, str] = {
    # Legacy (Phase 1-4)
    "CET1_CAPITAL": "RCRI",  # RC-R Part I (risk-based capital)
    "HTM_FAIRVAL": "RCB",  # RC-B (securities) — HTM fair value line item
    # Phase 5.1 — Schedule RI (income statement)
    "RI_INT_LOANS": "RI",
    "RI_INT_LEASE": "RI",
    "RI_INT_DEPBAL": "RI",
    "RI_INT_TRD": "RI",
    "RI_INT_FF": "RI",
    "RI_INT_INC_TOT": "RI",
    "RI_INT_EXP_TOT": "RI",
    "RI_NET_INT_INC": "RI",
    "RI_PROV": "RI",
    "RI_NII_SVCCHG": "RI",
    "RI_NII_FIDU": "RI",
    "RI_NII_TRD": "RI",
    "RI_NII_INVBK": "RI",
    "RI_NII_TOT": "RI",
    "RI_NIX_SAL": "RI",
    "RI_NIX_PREM": "RI",
    "RI_NIX_OTH": "RI",
    "RI_NIX_TOT": "RI",
    "RI_PRETAX": "RI",
    "RI_TAX": "RI",
    "RI_NET_INC": "RI",
    # Phase 5.1 — Schedule RC (balance sheet)
    "RC_CASH_NIB": "RC",
    "RC_CASH_IB": "RC",
    "RC_SEC_HTM": "RC",
    "RC_SEC_AFS": "RC",
    "RC_FF_RESELL": "RC",
    "RC_LOANS_HFS": "RC",
    "RC_LOANS_GROSS": "RC",
    "RC_ACL": "RC",
    "RC_LOANS_NET": "RC",
    "RC_PREMISES": "RC",
    "RC_INTANGIBLES": "RC",
    "RC_OTHER_ASSETS": "RC",
    "RC_TOTAL_ASSETS": "RC",
    "RC_DEP_NIB": "RC",
    "RC_DEP_IB": "RC",
    "RC_DEP_TOTAL": "RC",
    "RC_OTHER_BORROW": "RC",
    "RC_SUBORD": "RC",
    "RC_OTHER_LIAB": "RC",
    "RC_TOTAL_LIAB": "RC",
    "RC_COMMON_STOCK": "RC",
    "RC_SURPLUS": "RC",
    "RC_RETAINED": "RC",
    "RC_AOCI": "RC",
    "RC_BANK_EQUITY": "RC",
}

# 24-quarter window covers Phase 5.1's historical backfill (2020-Q1 onward).
# Daily cron still re-fetches only the trailing 8; older quarters are pulled
# once via `peerbench backfill` after manual ZIP placement per
# docs/cdr-backfill.md.
_QUARTERS: tuple[str, ...] = (
    "2020-Q1",
    "2020-Q2",
    "2020-Q3",
    "2020-Q4",
    "2021-Q1",
    "2021-Q2",
    "2021-Q3",
    "2021-Q4",
    "2022-Q1",
    "2022-Q2",
    "2022-Q3",
    "2022-Q4",
    "2023-Q1",
    "2023-Q2",
    "2023-Q3",
    "2023-Q4",
    "2024-Q1",
    "2024-Q2",
    "2024-Q3",
    "2024-Q4",
    "2025-Q1",
    "2025-Q2",
    "2025-Q3",
    "2025-Q4",
)

# Stable MDRM candidates across the 24-quarter window. Each value is a tuple
# of column names; the first non-empty value per row is the bank's reported
# value. Order = preference (most-populous filer population first).
#
# RIAD codes (Schedule RI) have NO domain split — income is reported once
# at consolidated level. RCFD/RCON pairs (Schedule RC, RC-B) are
# consolidated/domestic. RCON/RCFN pairs (deposits) are reversed.
_STABLE: dict[str, tuple[str, ...]] = {
    # ------------------------------------------------------------------
    # Phase 1-4 legacy: capital + HTM
    # ------------------------------------------------------------------
    # RC-R Part I.A line 26: CET1 capital amount, $. Domain split:
    #   RCOAP859 — domestic-only filers (no foreign offices)
    #   RCFAP859 — filers with foreign offices (e.g. First-Citizens)
    "CET1_CAPITAL": ("RCOAP859", "RCFAP859"),
    # RC-B line 5 ("Total securities, held-to-maturity, fair value"):
    # HTM securities fair value, $. Domain split:
    #   RCFD1771 — consolidated (foreign-office banks; e.g. First-Citizens
    #              reports $8.488B in 2025-Q4 against $9.645B amortized cost)
    #   RCON1771 — domestic only (the 4 of 5 sample banks without foreign
    #              offices populate this and leave RCFD1771 blank)
    # NEVER swap back to `1773` — that MDRM is AFS carrying value, not HTM.
    "HTM_FAIRVAL": ("RCFD1771", "RCON1771"),
    # ------------------------------------------------------------------
    # Schedule RI — income statement (consolidated, RIAD* only)
    # ------------------------------------------------------------------
    "RI_INT_LOANS": ("RIAD4010",),  # Interest and fees on loans
    "RI_INT_LEASE": ("RIAD4065",),  # Income from lease financing
    "RI_INT_DEPBAL": ("RIAD4115",),  # Interest on balances due from depositories
    "RI_INT_TRD": ("RIAD4069",),  # Interest income from trading assets
    "RI_INT_FF": ("RIAD4020",),  # Income on fed funds sold and securities purchased
    "RI_INT_INC_TOT": ("RIAD4107",),  # Total interest income (subtotal)
    "RI_INT_EXP_TOT": ("RIAD4073",),  # Total interest expense (subtotal)
    "RI_NET_INT_INC": ("RIAD4074",),  # Net interest income (subtotal)
    "RI_PROV": ("RIADJJ33",),  # Provision for credit losses (post-CECL)
    "RI_NII_SVCCHG": ("RIAD4080",),  # Service charges on deposit accounts
    "RI_NII_FIDU": ("RIAD4070",),  # Income from fiduciary activities
    "RI_NII_TRD": ("RIADA220",),  # Trading revenue
    "RI_NII_INVBK": ("RIADC888",),  # Investment banking, advisory, underwriting fees
    "RI_NII_TOT": ("RIAD4079",),  # Total noninterest income (subtotal)
    "RI_NIX_SAL": ("RIAD4135",),  # Salaries and employee benefits
    "RI_NIX_PREM": ("RIAD4217",),  # Expenses of premises and fixed assets
    "RI_NIX_OTH": ("RIAD4092",),  # Other noninterest expense
    "RI_NIX_TOT": ("RIAD4093",),  # Total noninterest expense (subtotal)
    "RI_PRETAX": ("RIAD4301",),  # Income before applicable income taxes (subtotal)
    "RI_TAX": ("RIAD4302",),  # Applicable income taxes
    "RI_NET_INC": ("RIAD4340",),  # Net income attributable to bank (subtotal)
    # ------------------------------------------------------------------
    # Schedule RC — balance sheet
    # RCFD = consolidated, RCON = domestic-only.
    # ------------------------------------------------------------------
    "RC_CASH_NIB": ("RCFD0081", "RCON0081"),  # Noninterest-bearing cash & coin
    "RC_CASH_IB": ("RCFD0071", "RCON0071"),  # Interest-bearing balances due
    "RC_SEC_HTM": ("RCFDJJ34", "RCONJJ34"),  # HTM securities (ASU 2016-13 / post-CECL)
    "RC_SEC_AFS": ("RCFD1773", "RCON1773"),  # AFS securities (carrying value = fair value)
    "RC_FF_RESELL": ("RCFDB989", "RCONB989"),  # Securities purchased under resale
    "RC_LOANS_HFS": ("RCFD5369", "RCON5369"),  # Loans and leases held for sale
    "RC_LOANS_GROSS": ("RCFDB528", "RCONB528"),  # Loans, net of unearned income
    "RC_ACL": ("RCFD3123", "RCON3123"),  # ACL on loans and leases (post-CECL)
    "RC_LOANS_NET": ("RCFDB529", "RCONB529"),  # Loans, net of unearned income and ACL
    "RC_PREMISES": ("RCFD2145", "RCON2145"),  # Premises & fixed assets (incl. ROU)
    "RC_INTANGIBLES": ("RCFD2143", "RCON2143"),  # Intangible assets (goodwill + other)
    "RC_OTHER_ASSETS": ("RCFD2160", "RCON2160"),  # Other assets
    "RC_TOTAL_ASSETS": ("RCFD2170", "RCON2170"),  # Total assets (subtotal)
    # Deposits use RCON (domestic-only filers) / RCFN (foreign-office filers).
    # The pair is reversed from RCFD/RCON but pick_first_non_empty is
    # domain-agnostic — order = preference (domestic-only is the larger
    # population in our peer set).
    "RC_DEP_NIB": ("RCON6631", "RCFN6631"),  # Noninterest-bearing deposits
    "RC_DEP_IB": ("RCON6636", "RCFN6636"),  # Interest-bearing deposits
    "RC_DEP_TOTAL": ("RCON2200", "RCFN2200"),  # Total deposits (subtotal)
    "RC_OTHER_BORROW": ("RCFD3190", "RCON3190"),  # Other borrowed money
    "RC_SUBORD": ("RCFD3200", "RCON3200"),  # Subordinated notes and debentures
    "RC_OTHER_LIAB": ("RCFD2930", "RCON2930"),  # Other liabilities
    "RC_TOTAL_LIAB": ("RCFD2948", "RCON2948"),  # Total liabilities (subtotal)
    "RC_COMMON_STOCK": ("RCFD3230", "RCON3230"),  # Common stock par
    "RC_SURPLUS": ("RCFD3839", "RCON3839"),  # Surplus (paid-in capital)
    "RC_RETAINED": ("RCFD3632", "RCON3632"),  # Retained earnings (undivided profits)
    "RC_AOCI": ("RCFDB530", "RCONB530"),  # Accumulated OCI
    "RC_BANK_EQUITY": ("RCFD3210", "RCON3210"),  # Total bank equity capital (subtotal)
}

_OVERRIDES: dict[tuple[str, str], tuple[str, ...]] = {
    # Example shape if FFIEC restructures mid-window:
    # ("2026-Q1", "CET1_CAPITAL"): ("RCOAP860", "RCFAP860"),
    #
    # Known CECL-transition risk (pre-2020-Q2): MDRMs `RIADJJ33` (provision)
    # and `RCFDJJ34` / `RCFD3123` (HTM amortized cost, ACL post-CECL) may
    # not be populated for banks that adopted CECL late. If a backfill
    # report flags missing values for these MDRMs in pre-2020-Q2 quarters,
    # add quarter-specific overrides here pointing at the pre-CECL codes
    # (RIAD4230 for provision-for-loan-and-lease-losses; RCFD3123 is the
    # same MDRM number both pre- and post-CECL — it was retitled from
    # "ALLL" to ACL but the row didn't move, so no override is needed).
}

_SCHEMA: dict[tuple[str, str], tuple[str, ...]] = {
    (q, label): _STABLE[label] for q in _QUARTERS for label in _STABLE
} | _OVERRIDES


def cdr_columns(quarter_id: str, field_label: str) -> tuple[str, ...]:
    """Return the tuple of candidate MDRM columns for (quarter, label).

    Raises KeyError with a diagnostic message that lists known labels and
    quarters when the lookup misses. Callers must walk the returned tuple
    and take the first non-empty value per row (see
    `peerbench.ingest.cdr.pick_first_non_empty`).
    """
    key = (quarter_id, field_label)
    if key in _SCHEMA:
        return _SCHEMA[key]
    known_labels_list = sorted({lbl for _, lbl in _SCHEMA})
    known_quarters_list = sorted({q for q, _ in _SCHEMA})
    msg = (
        f"No CDR schema mapping for quarter={quarter_id!r}, "
        f"field={field_label!r}.\n"
        f"  Known labels:   {known_labels_list}\n"
        f"  Known quarters: {known_quarters_list}"
    )
    raise KeyError(msg)


def known_quarters() -> tuple[str, ...]:
    return _QUARTERS


def known_labels() -> tuple[str, ...]:
    return tuple(_STABLE.keys())


def known_keys() -> tuple[tuple[str, str], ...]:
    """Every `(quarter, label)` pair the schema maps — `_STABLE` rows ×
    `_QUARTERS`, plus every `_OVERRIDES` entry (which may include quarters
    not in `_QUARTERS`). Use this when a regression test must assert a
    property across every row the schema can return, including override
    edits made for future quarters."""
    return tuple(sorted(_SCHEMA))
