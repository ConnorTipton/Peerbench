"""FactView — read-only view over a bank's facts for one quarter (and the
prior 4 quarters, for 5-period averaging).

Handlers receive a FactView and return a Decimal. The FactView surface is
deliberately minimal: looking up a field code, requesting an average over
N periods, requesting an annualization factor. Day 3 fills in the handler
bodies; Day 2 just commits to this interface so the stubs type-check.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


class MissingFieldError(KeyError):
    """Raised when a handler asks for a field that wasn't in the fact set.

    The suppression layer catches this and records `data_quality='partial'`
    + a quality_log row rather than letting the whole compute pass fail.
    """


@dataclass(frozen=True)
class FactView:
    cert: int
    quarter_id: str
    quarter_number: int  # 1..4
    # Period-aligned: index 0 is the target quarter, indexes 1..N are the
    # N preceding quarters (most recent first). Each dict maps field_code → Decimal | None.
    facts_by_period: tuple[dict[str, Decimal | None], ...]

    @property
    def current(self) -> dict[str, Decimal | None]:
        return self.facts_by_period[0]

    def __contains__(self, field_code: str) -> bool:
        return field_code in self.current and self.current[field_code] is not None

    def __getitem__(self, field_code: str) -> Decimal:
        v = self.current.get(field_code)
        if v is None:
            raise MissingFieldError(field_code)
        return v

    def get(self, field_code: str, default: Decimal | None = None) -> Decimal | None:
        v = self.current.get(field_code)
        return v if v is not None else default

    def avg(self, field_code: str, *, periods: int) -> Decimal:
        """Average a field across the most recent `periods` quarters.

        FDIC's 5-period YTD averaging convention: include the current quarter
        and the 4 preceding ones (i.e. periods=5 = 5 distinct quarter values).
        Refuses to average if any required period is missing — better to
        surface the gap as 'partial' than to silently understate.
        """
        if periods < 1 or periods > len(self.facts_by_period):
            msg = (
                f"avg(periods={periods}) requires {periods} period(s); "
                f"FactView has {len(self.facts_by_period)}"
            )
            raise MissingFieldError(msg)
        values: list[Decimal] = []
        for i in range(periods):
            v = self.facts_by_period[i].get(field_code)
            if v is None:
                raise MissingFieldError(f"{field_code} missing in period offset {i}")
            values.append(v)
        return sum(values, Decimal(0)) / Decimal(periods)

    def annualize_factor(self) -> Decimal:
        """YTD-to-annual multiplier per FDIC convention.

        Q1 × 4 (only 1 quarter of YTD accumulation)
        Q2 × 2
        Q3 × 4/3
        Q4 × 1 (full year already)
        """
        return {
            1: Decimal(4),
            2: Decimal(2),
            3: Decimal(4) / Decimal(3),
            4: Decimal(1),
        }[self.quarter_number]
