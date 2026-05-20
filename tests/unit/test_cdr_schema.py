"""Unit tests for the CDR per-quarter schema map."""

from __future__ import annotations

import pytest

from peerbench.ingest.cdr_schema import (
    SCHEDULE_PATTERN,
    cdr_column,
    known_labels,
    known_quarters,
)


def test_all_8_quarters_resolve_all_labels() -> None:
    """5 banks × 8 quarters is the validation grid; both labels must resolve."""
    quarters = known_quarters()
    assert len(quarters) == 8
    labels = known_labels()
    assert set(labels) == {"CET1_CAPITAL", "HTM_FAIRVAL"}
    for q in quarters:
        for lbl in labels:
            mdrm = cdr_column(q, lbl)
            assert mdrm.startswith(("RCO", "RCF")), (
                f"{q}/{lbl} -> {mdrm!r} doesn't look like an MDRM"
            )


def test_schedule_pattern_covers_all_labels() -> None:
    for lbl in known_labels():
        assert lbl in SCHEDULE_PATTERN
        assert SCHEDULE_PATTERN[lbl]


def test_unknown_quarter_raises_keyerror_with_diagnostic() -> None:
    with pytest.raises(KeyError) as exc:
        cdr_column("2019-Q1", "CET1_CAPITAL")
    msg = str(exc.value)
    assert "2019-Q1" in msg
    assert "Known quarters" in msg


def test_unknown_label_raises_keyerror_with_diagnostic() -> None:
    with pytest.raises(KeyError) as exc:
        cdr_column("2025-Q4", "NOT_A_LABEL")
    msg = str(exc.value)
    assert "NOT_A_LABEL" in msg
    assert "Known labels" in msg


def test_stable_codes_match_documented_values() -> None:
    """Pin the documented MDRMs so silent drift is caught.

    These are flagged TODO-verify in cdr_schema.py — when Step 7 of the
    Task 25 plan verifies against a real ZIP, update both the schema map
    and this pin.
    """
    assert cdr_column("2025-Q4", "CET1_CAPITAL") == "RCOA8274"
    assert cdr_column("2025-Q4", "HTM_FAIRVAL") == "RCFD1773"
