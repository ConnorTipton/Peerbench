"""Restatement-detector callback for `upsert_fact`.

`make_quality_log_callback(session)` returns an `OnDiffCallback` that:

  1. Writes a `quality_log` row with `event_type='restated'`, old + new
     values, cert + quarter_id + field_code.
  2. Flips every `ratios` row for the affected `(cert, quarter_id)` to
     `data_quality='partial'` — the next `peerbench compute` run will
     promote those rows back to `'ok'` once they've been recomputed.

Both operations run inside the caller's SQLAlchemy session — no commit,
no sub-transaction. Atomicity flows from the surrounding `with
get_session()` block: if the ingest rolls back, the log row and the
partial flag roll back with it.

Decision rationale and the delete-vs-partial trade-off are recorded in
`~/.claude/plans/enter-plan-mode-goal-memoized-fiddle.md` (Day 4 plan,
decision 3).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import update
from sqlalchemy.orm import Session

from peerbench.db.models import QualityLog, Ratio
from peerbench.ingest.upsert import OnDiffCallback


def make_quality_log_callback(session: Session) -> OnDiffCallback:
    """Return a callback bound to `session` for use as `upsert_fact(on_diff=...)`."""

    def _callback(
        cert: int,
        quarter_id: str,
        field_code: str,
        old: Decimal | None,
        new: Decimal | None,
    ) -> None:
        # `upsert_fact` already returns early on first insert, so this
        # callback only fires when an existing fact's value changed.
        # Defensive double-guard: a future caller could invoke on_diff
        # directly with no real diff (e.g. both sides None) — no-op then.
        if old is None and new is None:
            return
        session.add(
            QualityLog(
                cert=cert,
                quarter_id=quarter_id,
                field_code=field_code,
                event_type="restated",
                old_value=old,
                new_value=new,
                detected_at=datetime.now(UTC),
            )
        )
        session.execute(
            update(Ratio)
            .where(Ratio.cert == cert, Ratio.quarter_id == quarter_id)
            .values(data_quality="partial")
        )

    return _callback
