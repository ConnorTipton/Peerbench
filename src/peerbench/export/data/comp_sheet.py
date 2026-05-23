"""Build the Comp Sheet tab payloads — one per peer (anchor excluded)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from peerbench.export.data.types import (
    BalanceSheetLine,
    CompRatioRow,
    CompSheetTab,
    IncomeStatementLine,
)
from peerbench.export.directions import direction_for


@dataclass(frozen=True)
class _LineSpec:
    label: str
    field_code: str


INCOME_STATEMENT_LINES: tuple[_LineSpec, ...] = (
    _LineSpec("Interest income", "INTINC"),
    _LineSpec("Interest expense", "EINTEXP"),
    _LineSpec("Net interest income", "NIM"),
    _LineSpec("Provision for credit losses", "ELNATR"),
    _LineSpec("Non-interest income", "NONII"),
    _LineSpec("Non-interest expense", "NONIX"),
    _LineSpec("Net income", "NETINC"),
)

BALANCE_SHEET_LINES: tuple[_LineSpec, ...] = (
    _LineSpec("Total assets", "ASSET"),
    _LineSpec("Loans (gross)", "LNLSGR"),
    _LineSpec("Securities", "SC"),
    _LineSpec("Cash & equivalents", "CHBAL"),
    _LineSpec("Total deposits", "DEP"),
    _LineSpec("Total liabilities", "LIAB"),
    _LineSpec("Total equity", "EQ"),
)

_INVALID_SHEET_CHARS = re.compile(r"[\[\]:*?/\\]")
_MAX_SHEET_NAME_LEN = 31


def sanitize_sheet_name(name: str, *, used: set[str] | None = None) -> str:
    """Sanitize + truncate to Excel's 31-char limit. Append numeric suffix on collision."""
    cleaned = _INVALID_SHEET_CHARS.sub("", name).strip()
    base = cleaned[:_MAX_SHEET_NAME_LEN]
    if used is None or base not in used:
        return base
    i = 2
    while True:
        suffix = f"-{i}"
        truncated = base[: _MAX_SHEET_NAME_LEN - len(suffix)]
        candidate = f"{truncated}{suffix}"
        if candidate not in used:
            return candidate
        i += 1


class RatioDefLike(Protocol):
    ratio_id: str
    display_name: str
    category: str
    numerator_formula: str
    denominator_formula: str


def build_comp_sheets(
    *,
    anchor: tuple[int, str],
    peers: list[tuple[int, str]],
    quarter_id: str,
    income_statement_quarter_ids: list[str],
    facts_by_cert_quarter: dict[tuple[int, str], dict[str, Decimal | None]],
    ratios_by_cert: dict[int, dict[str, Decimal | None]],
    ratio_defs: list[RatioDefLike],
) -> list[CompSheetTab]:
    used_sheet_names: set[str] = set()
    sheets: list[CompSheetTab] = []
    anchor_cert, anchor_name = anchor

    for peer_cert, peer_name in peers:
        sheet_name = sanitize_sheet_name(peer_name, used=used_sheet_names)
        used_sheet_names.add(sheet_name)

        income_lines: list[IncomeStatementLine] = []
        for spec in INCOME_STATEMENT_LINES:
            anchor_values = [
                facts_by_cert_quarter.get((anchor_cert, q), {}).get(spec.field_code)
                for q in income_statement_quarter_ids
            ]
            peer_values = [
                facts_by_cert_quarter.get((peer_cert, q), {}).get(spec.field_code)
                for q in income_statement_quarter_ids
            ]
            income_lines.append(
                IncomeStatementLine(
                    label=spec.label,
                    field_code=spec.field_code,
                    anchor_values=anchor_values,
                    peer_values=peer_values,
                )
            )

        balance_lines: list[BalanceSheetLine] = []
        anchor_facts = facts_by_cert_quarter.get((anchor_cert, quarter_id), {})
        peer_facts = facts_by_cert_quarter.get((peer_cert, quarter_id), {})
        for spec in BALANCE_SHEET_LINES:
            balance_lines.append(
                BalanceSheetLine(
                    label=spec.label,
                    field_code=spec.field_code,
                    anchor_value=anchor_facts.get(spec.field_code),
                    peer_value=peer_facts.get(spec.field_code),
                )
            )

        ratio_rows: list[CompRatioRow] = []
        anchor_ratios = ratios_by_cert.get(anchor_cert, {})
        peer_ratios = ratios_by_cert.get(peer_cert, {})
        for r in ratio_defs:
            ratio_rows.append(
                CompRatioRow(
                    ratio_id=r.ratio_id,
                    display_name=r.display_name,
                    category=r.category,
                    formula=f"{r.numerator_formula} / {r.denominator_formula}",
                    anchor_value=anchor_ratios.get(r.ratio_id),
                    peer_value=peer_ratios.get(r.ratio_id),
                    direction=direction_for(r.ratio_id),
                )
            )

        sheets.append(
            CompSheetTab(
                sheet_name=sheet_name,
                peer_cert=peer_cert,
                peer_name=peer_name,
                anchor_cert=anchor_cert,
                anchor_name=anchor_name,
                quarter_id=quarter_id,
                income_statement_quarters=income_statement_quarter_ids,
                income_statement=income_lines,
                balance_sheet=balance_lines,
                ratios=ratio_rows,
            )
        )
    return sheets
