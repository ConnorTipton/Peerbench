"""Fact upsert with an `on_diff` callback seam.

Day 2 scaffolds the seam; Day 3 fills in the callback that writes
`quality_log` and marks affected ratios stale. The callback signature
passes `old: Decimal | None` so a Day 3 implementation can no-op on the
first insert (no diff to report).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from peerbench.db.models import Fact

OnDiffCallback = Callable[[int, str, str, Decimal | None, Decimal | None], None]


def upsert_fact(
    session: Session,
    cert: int,
    quarter_id: str,
    field_code: str,
    value: Decimal | None,
    on_diff: OnDiffCallback | None = None,
) -> None:
    """Insert-or-update a single fact row. Decimal-exact comparison only.

    No tolerance, no float — equality is `old != new` on Decimal directly.
    The restatement detector relies on this; any softening here would hide
    legitimate small restatements.
    """
    now = datetime.now(UTC)
    existing = session.get(Fact, (cert, quarter_id, field_code))
    if existing is None:
        session.add(
            Fact(
                cert=cert,
                quarter_id=quarter_id,
                field_code=field_code,
                value=value,
                first_seen_at=now,
                last_updated_at=now,
            )
        )
        return
    if existing.value != value:
        old = existing.value
        existing.value = value
        existing.last_updated_at = now
        existing.restated = True
        # The existing-row branch only — first inserts return above, never
        # reach here. NULL→value and value→NULL are legitimate restatements
        # the Day 3 quality_log writer must see.
        if on_diff is not None:
            on_diff(cert, quarter_id, field_code, old, value)
