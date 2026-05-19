"""Persist RatioResult to the `ratios` table via idempotent upsert."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from peerbench.db.models import Ratio
from peerbench.ratio_engine.compute import (
    OkResult,
    PartialResult,
    RatioResult,
    SuppressedResult,
    data_quality_for,
)


def _value_of(result: RatioResult) -> Decimal | None:
    if isinstance(result, OkResult):
        return result.value
    if isinstance(result, PartialResult):
        return result.value
    if isinstance(result, SuppressedResult):
        return None
    msg = f"unknown ratio result type: {type(result).__name__}"
    raise TypeError(msg)


def upsert_ratio(
    session: Session,
    cert: int,
    quarter_id: str,
    ratio_id: str,
    result: RatioResult,
    formula_version: str,
) -> None:
    stmt = pg_insert(Ratio).values(
        cert=cert,
        quarter_id=quarter_id,
        ratio_id=ratio_id,
        value=_value_of(result),
        formula_version=formula_version,
        data_quality=data_quality_for(result),
        computed_at=datetime.now(UTC),
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["cert", "quarter_id", "ratio_id"],
        set_={
            "value": stmt.excluded.value,
            "formula_version": stmt.excluded.formula_version,
            "data_quality": stmt.excluded.data_quality,
            "computed_at": stmt.excluded.computed_at,
        },
    )
    session.execute(stmt)
