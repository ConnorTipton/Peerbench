"""SQLAlchemy 2.x typed declarative models.

Mirrors `sql/schema.sql`. NUMERIC columns return `Decimal` (never `float`) —
this is non-negotiable for the <2 bps DoD. JSONB columns are typed as
`dict[str, Any]`.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Institution(Base):
    __tablename__ = "institutions"

    cert: Mapped[int] = mapped_column(Integer, primary_key=True)
    rssd: Mapped[int | None] = mapped_column(Integer, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    charter: Mapped[str | None] = mapped_column(Text)
    state: Mapped[str | None] = mapped_column(Text)
    hq_city: Mapped[str | None] = mapped_column(Text)
    asset_band: Mapped[str | None] = mapped_column(Text)
    peer_tier: Mapped[int | None] = mapped_column(SmallInteger)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    acquired_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("institutions.cert"))


class Quarter(Base):
    __tablename__ = "quarters"
    __table_args__ = (CheckConstraint("source IN ('fdic_api','ffiec_cdr')"),)

    quarter_id: Mapped[str] = mapped_column(Text, primary_key=True)  # 'YYYY-Qn'
    year: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    quarter: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    ingest_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)


class Fact(Base):
    __tablename__ = "facts"

    cert: Mapped[int] = mapped_column(Integer, ForeignKey("institutions.cert"), primary_key=True)
    quarter_id: Mapped[str] = mapped_column(
        Text, ForeignKey("quarters.quarter_id"), primary_key=True
    )
    field_code: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[Decimal | None] = mapped_column(Numeric)
    restated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RatioDef(Base):
    __tablename__ = "ratio_defs"
    __table_args__ = (CheckConstraint("avg_or_eop IN ('AVG','EOP')"),)

    ratio_id: Mapped[str] = mapped_column(Text, primary_key=True)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    numerator_formula: Mapped[str] = mapped_column(Text, nullable=False)
    denominator_formula: Mapped[str] = mapped_column(Text, nullable=False)
    annualize: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    avg_or_eop: Mapped[str] = mapped_column(Text, nullable=False)
    fdic_precomputed_code: Mapped[str | None] = mapped_column(Text)
    ubpr_concept: Mapped[str | None] = mapped_column(Text)
    regulatory_threshold: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    suppress_when: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    notes: Mapped[str | None] = mapped_column(Text)


class Ratio(Base):
    __tablename__ = "ratios"
    __table_args__ = (CheckConstraint("data_quality IN ('ok','partial','suppressed','mismatch')"),)

    cert: Mapped[int] = mapped_column(Integer, primary_key=True)
    quarter_id: Mapped[str] = mapped_column(Text, primary_key=True)
    ratio_id: Mapped[str] = mapped_column(Text, ForeignKey("ratio_defs.ratio_id"), primary_key=True)
    value: Mapped[Decimal | None] = mapped_column(Numeric)
    formula_version: Mapped[str] = mapped_column(Text, nullable=False)
    data_quality: Mapped[str] = mapped_column(Text, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class QualityLog(Base):
    __tablename__ = "quality_log"
    __table_args__ = (
        CheckConstraint("event_type IN ('missing','suppressed','restated','mismatch')"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cert: Mapped[int | None] = mapped_column(Integer)
    quarter_id: Mapped[str | None] = mapped_column(Text)
    field_code: Mapped[str | None] = mapped_column(Text)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    old_value: Mapped[Decimal | None] = mapped_column(Numeric)
    new_value: Mapped[Decimal | None] = mapped_column(Numeric)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
