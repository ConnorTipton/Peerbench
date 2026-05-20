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

Stable field labels (`CET1_CAPITAL`, `HTM_FAIRVAL`) are the pipeline's
internal identifiers. The TSV column is the per-quarter MDRM code that
appears in the bulk file header. `SCHEDULE_PATTERN` maps each label to
the substring used to locate the right schedule file inside the ZIP.

Scope
-----
Maps only the 8 quarters Peerbench actively ingests (2024-Q1 through
2025-Q4 as of 2026-05-20). Older quarters raise KeyError with a clear
message — historical backfill is a Phase 3 concern.

Empirical pinning (2026-05-20)
-----------------------------
`P859` (CET1 capital amount) verified against Bank OZK (cert 110) live
CDR ZIPs: `RCOAP859 / RWAJT = 11.7244%` matches FDIC `IDT1CER` exactly.
Pre-CECL `RCOA8274` (Tier 1 capital amount) over-stated by 77 bps for
banks with AT1 preferred stock (CET1 < Tier 1). `RCFD1773` (HTM fair
value, RC-B Memo 2(d)) confirmed consolidated-domestic.
"""

from __future__ import annotations

# Field label → substring used to locate the right schedule file(s) inside
# the Subject Data Format ZIP. FFIEC names schedule files like
# `FFIEC CDR Call Schedule RCRI 12312025.txt` (single-file) or
# `FFIEC CDR Call Schedule RCB 12312025(1 of 2).txt` (split). The 4-letter
# token is the discriminator; multi-file fan-in is handled in cdr.py.
SCHEDULE_PATTERN: dict[str, str] = {
    "CET1_CAPITAL": "RCRI",  # RC-R Part I (risk-based capital)
    "HTM_FAIRVAL": "RCB",  # RC-B (securities)
}

_QUARTERS: tuple[str, ...] = (
    "2024-Q1",
    "2024-Q2",
    "2024-Q3",
    "2024-Q4",
    "2025-Q1",
    "2025-Q2",
    "2025-Q3",
    "2025-Q4",
)

# Stable MDRM candidates across the 2024-2025 window. Each value is a
# tuple of column names; the first non-empty value per row is the bank's
# reported value. Order = preference (RCOA before RCFA for CET1 because
# the domestic-only population is larger).
_STABLE: dict[str, tuple[str, ...]] = {
    # RC-R Part I.A line 26: CET1 capital amount, $. Domain split:
    #   RCOAP859 — domestic-only filers (no foreign offices)
    #   RCFAP859 — filers with foreign offices (e.g. First-Citizens)
    "CET1_CAPITAL": ("RCOAP859", "RCFAP859"),
    # RC-B Memorandum 2(d): HTM securities fair value, $.
    "HTM_FAIRVAL": ("RCFD1773",),
}

_OVERRIDES: dict[tuple[str, str], tuple[str, ...]] = {
    # Example shape if FFIEC restructures mid-window:
    # ("2026-Q1", "CET1_CAPITAL"): ("RCOAP860", "RCFAP860"),
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
