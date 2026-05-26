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

Empirical pinning (2026-05-20, HTM fix 2026-05-25)
--------------------------------------------------
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
    # RC-B line 5 ("Total securities, held-to-maturity, fair value"):
    # HTM securities fair value, $. Domain split:
    #   RCFD1771 — consolidated (foreign-office banks; e.g. First-Citizens
    #              reports $8.488B in 2025-Q4 against $9.645B amortized cost)
    #   RCON1771 — domestic only (the 4 of 5 sample banks without foreign
    #              offices populate this and leave RCFD1771 blank)
    # NEVER swap back to `1773` — that MDRM is AFS carrying value, not HTM.
    "HTM_FAIRVAL": ("RCFD1771", "RCON1771"),
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


def known_keys() -> tuple[tuple[str, str], ...]:
    """Every `(quarter, label)` pair the schema maps — `_STABLE` rows ×
    `_QUARTERS`, plus every `_OVERRIDES` entry (which may include quarters
    not in `_QUARTERS`). Use this when a regression test must assert a
    property across every row the schema can return, including override
    edits made for future quarters."""
    return tuple(sorted(_SCHEMA))
