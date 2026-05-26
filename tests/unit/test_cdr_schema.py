"""Unit tests for the CDR per-quarter schema map."""

from __future__ import annotations

import pytest

from peerbench.ingest.cdr_schema import (
    SCHEDULE_PATTERN,
    cdr_columns,
    known_keys,
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
            mdrms = cdr_columns(q, lbl)
            assert isinstance(mdrms, tuple) and mdrms, (
                f"{q}/{lbl} -> {mdrms!r} must be a non-empty tuple"
            )
            for mdrm in mdrms:
                assert mdrm.startswith(("RCO", "RCF")), (
                    f"{q}/{lbl} -> {mdrm!r} doesn't look like an MDRM"
                )


def test_schedule_pattern_covers_all_labels() -> None:
    for lbl in known_labels():
        assert lbl in SCHEDULE_PATTERN
        assert SCHEDULE_PATTERN[lbl]


def test_unknown_quarter_raises_keyerror_with_diagnostic() -> None:
    with pytest.raises(KeyError) as exc:
        cdr_columns("2019-Q1", "CET1_CAPITAL")
    msg = str(exc.value)
    assert "2019-Q1" in msg
    assert "Known quarters" in msg


def test_unknown_label_raises_keyerror_with_diagnostic() -> None:
    with pytest.raises(KeyError) as exc:
        cdr_columns("2025-Q4", "NOT_A_LABEL")
    msg = str(exc.value)
    assert "NOT_A_LABEL" in msg
    assert "Known labels" in msg


def test_cet1_has_both_domain_prefix_candidates() -> None:
    """Domestic-only filers report CET1 under RCOAP859; banks with foreign
    offices (e.g. First-Citizens, cert 11063) report under RCFAP859.
    Both must be queryable so multi-column fallback can pick whichever the
    bank actually populated."""
    assert cdr_columns("2025-Q4", "CET1_CAPITAL") == ("RCOAP859", "RCFAP859")


def test_htm_fairval_has_both_domain_prefix_candidates() -> None:
    """RC-B line 5 ("Total securities, held-to-maturity, fair value") splits
    by domain: foreign-office banks populate `RCFD1771` (consolidated),
    domestic-only banks populate `RCON1771`. Empirically confirmed against
    the 2025-Q4 ZIP: First-Citizens (cert 11063) reports RCFD1771 = $8.488B
    HTM fair value (vs $9.645B amortized cost = $1.157B unrealized loss);
    the other 4 sample banks use RCON1771."""
    assert cdr_columns("2025-Q4", "HTM_FAIRVAL") == ("RCFD1771", "RCON1771")


def test_htm_fairval_not_mistaken_for_afs() -> None:
    """Regression guard: MDRM `1773` in Schedule RC-B is labelled
    "AVAILABLE-FOR-SALE SECURITIES" — it is the AFS carrying value, not HTM.
    The original mapping pointed at `1773` and silently floored htm_loss_t1
    to 0% for every bank because `SCHA (HTM book) - 1773 (AFS book)` is
    always negative.

    Iterate `known_keys()` (not just `known_quarters()`) so a hand-edit
    to `_OVERRIDES` for a future quarter that reverts to `1773` also
    trips this guard, not just edits inside the `_QUARTERS` window."""
    for quarter, label in known_keys():
        if label != "HTM_FAIRVAL":
            continue
        mdrms = cdr_columns(quarter, label)
        assert "RCFD1773" not in mdrms, f"{quarter}: 1773 is AFS, not HTM"
        assert "RCON1773" not in mdrms, f"{quarter}: 1773 is AFS, not HTM"
        assert all(m.endswith("1771") for m in mdrms), (
            f"{quarter}: HTM_FAIRVAL must use MDRM 1771, got {mdrms}"
        )
