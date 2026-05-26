"""Contract: data/statement_lines.csv ⇄ peerbench.fdic_fields.CDR_FIELDS.

Every `field_code` referenced in the CSV must be a code the ingest
pipeline actually writes to `facts.field_code`. Drift in either direction
would surface as silently-empty rows on the /statements view (CSV
references a code that's not ingested) or as orphaned ingest output (a
CDR_* field with no statement-line referencing it — wasted bytes).
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from peerbench.config import REPO_ROOT
from peerbench.fdic_fields import CDR_FIELDS


CSV_PATH = REPO_ROOT / "data" / "statement_lines.csv"


def _read_csv_rows() -> list[dict[str, str]]:
    with CSV_PATH.open() as fh:
        return list(csv.DictReader(fh))


# Phase 1-4 legacy CDR codes that intentionally have no statement_line row.
# They're inputs to specific ratio handlers (`cet1`, `htm_loss_t1`), not
# line items rendered on the /statements view. Track explicitly so the
# bidirectional contract test below catches any *new* drift.
LEGACY_NON_STATEMENT_CODES: frozenset[str] = frozenset({"CDR_CET1_CAPITAL", "CDR_HTM_FAIRVAL"})


@pytest.mark.contract
def test_csv_field_codes_subset_of_cdr_fields() -> None:
    """Every non-null field_code in the CSV must be in CDR_FIELDS so the
    ingest pipeline will populate it. Header rows (field_code blank) are
    ignored — they're pure structure."""
    rows = _read_csv_rows()
    csv_codes = {r["field_code"] for r in rows if r["field_code"]}
    missing = sorted(csv_codes - set(CDR_FIELDS))
    assert not missing, (
        f"statement_lines.csv references field_codes the ingest pipeline "
        f"will never populate: {missing}. "
        f"Add them to peerbench.ingest.cdr_schema._STABLE."
    )


@pytest.mark.contract
def test_cdr_fields_covered_by_csv_or_legacy_carveout() -> None:
    """Reverse direction: every CDR_* field the pipeline ingests should
    either (a) have a row in statement_lines.csv that renders it on the
    /statements view, or (b) be in LEGACY_NON_STATEMENT_CODES (handler
    inputs, intentionally not displayed). Catches the silent-orphan case:
    a new MDRM added to `_STABLE` that no statement_line ever references."""
    rows = _read_csv_rows()
    csv_codes = {r["field_code"] for r in rows if r["field_code"]}
    orphans = sorted(set(CDR_FIELDS) - csv_codes - LEGACY_NON_STATEMENT_CODES)
    assert not orphans, (
        f"CDR fields exist in the schema but have no statement_lines.csv row "
        f"and are not in LEGACY_NON_STATEMENT_CODES: {orphans}. "
        f"Either add a statement_lines.csv row for them or, if they are pure "
        f"handler inputs, append them to LEGACY_NON_STATEMENT_CODES with a "
        f"comment explaining why they don't render."
    )


@pytest.mark.contract
def test_parent_line_ids_reference_real_lines() -> None:
    """parent_line_id is a foreign key inside the CSV — typos would surface
    later as orphaned children in the rendered tree."""
    rows = _read_csv_rows()
    ids = {r["line_id"] for r in rows}
    for r in rows:
        parent = r.get("parent_line_id", "") or ""
        if parent:
            assert parent in ids, (
                f"row {r['line_id']!r} has parent_line_id={parent!r} which is not a real line_id"
            )


@pytest.mark.contract
def test_indent_consistent_with_parent() -> None:
    """A child row's indent_depth should be > its parent's. Catches manual
    edits where indent and tree structure desync."""
    rows = _read_csv_rows()
    by_id = {r["line_id"]: r for r in rows}
    for r in rows:
        parent = r.get("parent_line_id", "") or ""
        if not parent:
            continue
        child_depth = int(r["indent_depth"])
        parent_depth = int(by_id[parent]["indent_depth"])
        assert child_depth > parent_depth, (
            f"row {r['line_id']!r} indent={child_depth} but parent "
            f"{parent!r} indent={parent_depth}"
        )


@pytest.mark.contract
def test_line_ids_unique() -> None:
    rows = _read_csv_rows()
    ids = [r["line_id"] for r in rows]
    assert len(ids) == len(set(ids)), "duplicate line_id values in CSV"


@pytest.mark.contract
def test_subtotals_are_at_root_indent() -> None:
    """Subtotals close out the section they sum — they should land at the
    same indent as the section header, not nested inside a child block.
    Deposit total (RC_DEP_TOTAL) is a known exception: it sits inside the
    Liabilities section as a sub-roll-up of nib + ib deposits."""
    rows = _read_csv_rows()
    known_exceptions = {"RC_DEP_TOTAL"}
    for r in rows:
        if r["is_subtotal"].strip().upper() != "TRUE":
            continue
        if r["line_id"] in known_exceptions:
            continue
        assert int(r["indent_depth"]) == 0, (
            f"subtotal {r['line_id']!r} has indent_depth="
            f"{r['indent_depth']!r}; expected 0 (or add to known_exceptions)"
        )
