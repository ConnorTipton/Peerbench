"""Per-quarter column-name lookup for FFIEC CDR schedule TSVs.

CDR schedule TSVs do not have stable column names across quarters — RC-R
was restructured for the CECL transition (March 2019), and FFIEC
periodically renumbers MDRM codes. Rather than guessing at runtime, we
pin the column name per quarter in a lookup table here.

Usage
-----
    >>> from peerbench.ingest.cdr_schema import cdr_column, SCHEDULE_PATTERN
    >>> cdr_column("2025-Q4", "CET1_CAPITAL")
    'RCOA8274'
    >>> SCHEDULE_PATTERN["CET1_CAPITAL"]
    'RCRI'

Stable field labels (`CET1_CAPITAL`, `HTM_FAIRVAL`) are the pipeline's
internal identifiers. The TSV column is the per-quarter MDRM code that
appears in the bulk file header. `SCHEDULE_PATTERN` maps each label to
the substring used to locate the right schedule file inside the ZIP.

Scope
-----
Maps only the 8 quarters Peerbench actively ingests (2024-Q1 through
2025-Q4 as of 2026-05-19). Older quarters raise KeyError with a clear
message — historical backfill is a Phase 3 concern.

TODO(live-verify): the MDRM codes below are sourced from the FFIEC
MDRM data dictionary (RC-R Part I.A line 26 for CET1 capital amount;
RC-B Memorandum 2(d) for HTM total fair value). The pre-`RCFD`/`RCOA`
domain prefix split is non-obvious — confirm against a real Subject
Data Format ZIP at Step 7 of the Task 25 plan, and adjust if needed.
"""

from __future__ import annotations

# Field label → substring used to locate the right schedule file inside
# the Subject Data Format ZIP. FFIEC names schedule files like
# `FFIEC CDR Call Schedule RCRI 12312025.txt` — the 4-letter token is
# the discriminator.
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

# Stable MDRMs across the 2024-2025 window. If a future quarter ships
# with a different code, drop a per-quarter override in `_OVERRIDES`.
_STABLE: dict[str, str] = {
    "CET1_CAPITAL": "RCOA8274",  # RC-R Part I.A line 26: CET1 capital, $
    "HTM_FAIRVAL": "RCFD1773",  # RC-B Memorandum 2(d): HTM securities fair value, $
}

_OVERRIDES: dict[tuple[str, str], str] = {
    # Example shape if FFIEC restructures mid-window:
    # ("2026-Q1", "CET1_CAPITAL"): "RCOA8275",
}

_SCHEMA: dict[tuple[str, str], str] = {
    (q, label): _STABLE[label] for q in _QUARTERS for label in _STABLE
} | _OVERRIDES


def cdr_column(quarter_id: str, field_label: str) -> str:
    """Return the TSV column name (MDRM code) for quarter+label.

    Raises KeyError with a diagnostic message that lists known labels and
    quarters when the lookup misses.
    """
    key = (quarter_id, field_label)
    if key in _SCHEMA:
        return _SCHEMA[key]
    known_labels = sorted({lbl for _, lbl in _SCHEMA})
    known_quarters = sorted({q for q, _ in _SCHEMA})
    msg = (
        f"No CDR schema mapping for quarter={quarter_id!r}, "
        f"field={field_label!r}.\n"
        f"  Known labels:   {known_labels}\n"
        f"  Known quarters: {known_quarters}"
    )
    raise KeyError(msg)


def known_quarters() -> tuple[str, ...]:
    return _QUARTERS


def known_labels() -> tuple[str, ...]:
    return tuple(_STABLE.keys())
