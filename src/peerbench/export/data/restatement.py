"""Build the Restatement Log tab payload from quality_log + field-deps snapshot."""

from __future__ import annotations

from typing import Any

from peerbench.export.data.comp_sheet import (
    BALANCE_SHEET_LINES,
    INCOME_STATEMENT_LINES,
)
from peerbench.export.data.types import RestatementRow, RestatementTab

_COMP_SHEET_FIELDS: frozenset[str] = frozenset(
    line.field_code for line in (*INCOME_STATEMENT_LINES, *BALANCE_SHEET_LINES)
)


def derive_affected_ratios(
    field_code: str,
    field_deps: dict[str, list[str]],
) -> list[str]:
    """Return ratio_ids whose handler reads the given field, in input order."""
    return [rid for rid, fields in field_deps.items() if field_code in fields]


def build_restatement_log(
    events: list[dict[str, Any]],
    *,
    bank_names: dict[int, str],
    field_deps: dict[str, list[str]],
    window: set[str],
) -> RestatementTab:
    """Filter quality_log restatement events to those relevant to the workbook.

    Filters: quarter_id ∈ window AND field_code is read by ≥1 workbook ratio.
    Sort: detected_at DESC, quarter_id DESC.
    """
    rows: list[RestatementRow] = []
    for ev in events:
        quarter_id = str(ev["quarter_id"])
        if quarter_id not in window:
            continue
        field_code = str(ev["field_code"])
        affected = derive_affected_ratios(field_code, field_deps)
        if not affected and field_code not in _COMP_SHEET_FIELDS:
            continue
        cert = int(ev["cert"])
        rows.append(
            RestatementRow(
                detected_at=ev["detected_at"],
                cert=cert,
                bank_name=bank_names.get(cert, f"Cert {cert}"),
                quarter_id=quarter_id,
                field_code=field_code,
                old_value=ev.get("old_value"),
                new_value=ev.get("new_value"),
                affected_ratios=affected,
            )
        )
    rows.sort(key=lambda r: (r.detected_at, r.quarter_id), reverse=True)
    return RestatementTab(rows=rows)
