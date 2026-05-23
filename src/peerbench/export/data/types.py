from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal

Direction = Literal["higher_is_positive", "higher_is_negative", "neutral"]
DataQuality = Literal["ok", "partial", "suppressed", "mismatch"]


@dataclass(frozen=True, slots=True)
class CoverTab:
    anchor_cert: int
    anchor_name: str
    quarter_id: str
    quarter_end: str
    generated_at: datetime
    data_vintage: str
    notes: list[str]


@dataclass(frozen=True, slots=True)
class SummaryRow:
    ratio_id: str
    display_name: str
    category: str
    anchor_value: Decimal | None
    peer_values: dict[int, Decimal | None]
    peer_median: Decimal | None
    anchor_rank: int | None
    delta_vs_median: Decimal | None
    direction: Direction
    amber_pct: Decimal | None
    red_pct: Decimal | None


@dataclass(frozen=True, slots=True)
class SummaryTab:
    institution_columns: list[tuple[int, str]]
    rows: list[SummaryRow]


@dataclass(frozen=True, slots=True)
class IncomeStatementLine:
    label: str
    field_code: str
    anchor_values: list[Decimal | None]
    peer_values: list[Decimal | None]


@dataclass(frozen=True, slots=True)
class BalanceSheetLine:
    label: str
    field_code: str
    anchor_value: Decimal | None
    peer_value: Decimal | None


@dataclass(frozen=True, slots=True)
class CompRatioRow:
    ratio_id: str
    display_name: str
    category: str
    formula: str
    anchor_value: Decimal | None
    peer_value: Decimal | None
    direction: Direction


@dataclass(frozen=True, slots=True)
class CompSheetTab:
    sheet_name: str
    peer_cert: int
    peer_name: str
    anchor_cert: int
    anchor_name: str
    quarter_id: str
    income_statement_quarters: list[str]
    income_statement: list[IncomeStatementLine]
    balance_sheet: list[BalanceSheetLine]
    ratios: list[CompRatioRow]


@dataclass(frozen=True, slots=True)
class TimeSeriesPoint:
    cert: int
    value: Decimal | None


@dataclass(frozen=True, slots=True)
class TimeSeriesBlock:
    ratio_id: str
    display_name: str
    formula: str
    direction: Direction
    quarter_ids: list[str]
    rows: list[tuple[int, str, list[Decimal | None]]]


@dataclass(frozen=True, slots=True)
class TimeSeriesTab:
    sheet_name: str
    category: str
    category_label: str
    blocks: list[TimeSeriesBlock]


@dataclass(frozen=True, slots=True)
class RestatementRow:
    detected_at: datetime
    cert: int
    bank_name: str
    quarter_id: str
    field_code: str
    old_value: Decimal | None
    new_value: Decimal | None
    affected_ratios: list[str]


@dataclass(frozen=True, slots=True)
class RestatementTab:
    rows: list[RestatementRow]


@dataclass(frozen=True, slots=True)
class MethodologyNote:
    label: str
    text: str


@dataclass(frozen=True, slots=True)
class MethodologyBlock:
    ratio_id: str
    display_name: str
    category: str
    formula: str
    source_fields: list[str]
    annualization: str
    basis: str
    fdic_precomputed: str | None
    regulatory_threshold: str | None
    notes: str | None


@dataclass(frozen=True, slots=True)
class MethodologyTab:
    intro_notes: list[MethodologyNote]
    blocks: list[MethodologyBlock]


@dataclass(frozen=True, slots=True)
class WorkbookBundle:
    cover: CoverTab
    summary: SummaryTab
    comp_sheets: list[CompSheetTab]
    time_series: list[TimeSeriesTab]
    restatement_log: RestatementTab | None
    methodology: MethodologyTab | None
