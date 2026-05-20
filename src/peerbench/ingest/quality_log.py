"""Restatement-detector callback for `upsert_fact`.

`make_quality_log_callback(session)` returns an `OnDiffCallback` that:

  1. Writes a `quality_log` row with `event_type='restated'`, old + new
     values, cert + quarter_id + field_code.
  2. Flips the `data_quality` of every `ratios` row that *reads* the restated
     field for `(cert, quarter_id)` to `'partial'`. The next `peerbench
     compute` run promotes those rows back to `'ok'`. Scoping the flip to
     consumer ratios — instead of every ratio for that bank/quarter — keeps
     the dashboard's restatement indicator and the data-quality dot honest:
     a NIM restatement no longer trips CET1, ACL, or liquidity cells.

The consumer set is derived from each handler's AST via
`peerbench.ratio_engine.field_deps.extract_field_deps` and cached on first
use. Importing `peerbench.ratio_engine` here is load-bearing: it triggers
handler registration so the extractor sees the full registry.

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

import peerbench.ratio_engine  # noqa: F401  # pyright: ignore[reportUnusedImport]
from peerbench.db.models import QualityLog, Ratio
from peerbench.ingest.upsert import OnDiffCallback
from peerbench.ratio_engine.field_deps import extract_field_deps

_ratios_by_field_cache: dict[str, frozenset[str]] | None = None


def _ratios_by_field() -> dict[str, frozenset[str]]:
    """Lazy-build the field_code -> {ratio_id} inverse of the handler deps.

    Lazy so import-time ordering (handlers must be registered first) is not
    a footgun for direct importers of this module.
    """
    global _ratios_by_field_cache
    cache = _ratios_by_field_cache
    if cache is None:
        inverse: dict[str, set[str]] = {}
        for ratio_id, fields in extract_field_deps().items():
            for field in fields:
                inverse.setdefault(field, set()).add(ratio_id)
        cache = {f: frozenset(r) for f, r in inverse.items()}
        _ratios_by_field_cache = cache
    return cache


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
        affected = _ratios_by_field().get(field_code)
        if not affected:
            # No registered consumer reads this field — log the restatement
            # but don't flip any ratios. Happens for ingested-but-unused
            # FFIEC codes (e.g. ones we keep around for future handlers).
            return
        session.execute(
            update(Ratio)
            .where(
                Ratio.cert == cert,
                Ratio.quarter_id == quarter_id,
                Ratio.ratio_id.in_(affected),
            )
            .values(data_quality="partial")
        )

    return _callback
