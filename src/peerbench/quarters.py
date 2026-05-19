"""Quarter math: 'YYYY-Qn' identifiers, end-dates, filing-deadline awareness."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

QUARTER_END_MONTHS: dict[int, tuple[int, int]] = {
    1: (3, 31),
    2: (6, 30),
    3: (9, 30),
    4: (12, 31),
}

# Call Reports are due 30 days after quarter end (35 days for banks with foreign
# offices). FDIC then publishes to the BankFind API after a processing window;
# in practice the most recent quarter doesn't show up in the API until ~60-90
# days after quarter end. 90 days is the conservative pick: it picks a quarter
# we know is published, never one that's still in the filing window.
PUBLICATION_LATENCY_DAYS = 90


def quarter_id(year: int, quarter: int) -> str:
    return f"{year}-Q{quarter}"


def parse_quarter_id(qid: str) -> tuple[int, int]:
    year_str, q_str = qid.split("-Q")
    return int(year_str), int(q_str)


def quarter_end_date(year: int, quarter: int) -> date:
    month, day = QUARTER_END_MONTHS[quarter]
    return date(year, month, day)


def previous_quarter(year: int, quarter: int) -> tuple[int, int]:
    if quarter == 1:
        return year - 1, 4
    return year, quarter - 1


def most_recent_finalized(today: date | None = None) -> tuple[int, int]:
    """Latest quarter whose filing deadline has elapsed by `today`."""
    today = today or datetime.now(UTC).date()
    candidates: list[tuple[int, int]] = []
    for offset in range(8):
        y = today.year
        q = ((today.month - 1) // 3) + 1
        for _ in range(offset):
            y, q = previous_quarter(y, q)
        candidates.append((y, q))
    for year, quarter in candidates:
        end = quarter_end_date(year, quarter)
        if today - end >= timedelta(days=PUBLICATION_LATENCY_DAYS):
            return year, quarter
    msg = "no finalized quarter found in the last 8 candidates"
    raise RuntimeError(msg)


def recent_finalized_quarters(n: int, today: date | None = None) -> list[str]:
    """The n most recent finalized quarters, newest first."""
    year, quarter = most_recent_finalized(today)
    out: list[str] = []
    for _ in range(n):
        out.append(quarter_id(year, quarter))
        year, quarter = previous_quarter(year, quarter)
    return out
