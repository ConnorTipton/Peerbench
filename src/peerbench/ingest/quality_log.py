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
  3. Flips the `data_quality` of every `ratios` row whose ``f.avg(...)``
     YTD-averaging window reaches back through the restated quarter for
     ``(cert, forward_quarter_id)``. Two handlers do YTD averaging today —
     ``nco_ratio`` (LNLSGR) and ``cost_funds`` (DEPI, transitive into
     ``nis``). Without this forward flip, a Q2 LNLSGR restatement would
     leave ``nco_ratio`` at Q3/Q4 marked ``ok`` even though the underlying
     average has shifted; the dashboard would render a stale value with
     no indicator until the next compute pass overwrote it.

The same-quarter consumer set is derived from each handler's AST via
`peerbench.ratio_engine.field_deps.extract_field_deps` and cached on first
use. The forward-quarter set comes from `extract_avg_field_deps`, the
subset that only counts ``f.avg(...)`` reads (direct ``f["FIELD"]`` reads
don't propagate forward — they're same-quarter only). Importing
`peerbench.ratio_engine` here is load-bearing: it triggers handler
registration so the extractor sees the full registry.

Both operations run inside the caller's SQLAlchemy session — no commit,
no sub-transaction. Atomicity flows from the surrounding `with
get_session()` block: if the ingest rolls back, the log row and the
partial flags roll back with them.

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
from peerbench.quarters import parse_quarter_id, quarter_id
from peerbench.ratio_engine.field_deps import extract_avg_field_deps, extract_field_deps

_ratios_by_field_cache: dict[str, frozenset[str]] | None = None
_avg_consumers_by_field_cache: dict[str, frozenset[str]] | None = None


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


def _avg_consumers_by_field() -> dict[str, frozenset[str]]:
    """Lazy-build the field_code -> {ratio_id} inverse for ``f.avg(...)`` reads.

    Strict subset of :func:`_ratios_by_field`. Today: ``LNLSGR -> {nco_ratio}``
    and ``DEPI -> {cost_funds, nis}`` (``nis`` transitively via
    ``RATIO_DEPENDENCIES``).
    """
    global _avg_consumers_by_field_cache
    cache = _avg_consumers_by_field_cache
    if cache is None:
        inverse: dict[str, set[str]] = {}
        for ratio_id, fields in extract_avg_field_deps().items():
            for field in fields:
                inverse.setdefault(field, set()).add(ratio_id)
        cache = {f: frozenset(r) for f, r in inverse.items()}
        _avg_consumers_by_field_cache = cache
    return cache


def _ytd_forward_quarters(restated_quarter_id: str) -> list[str]:
    """Quarters whose YTD average reaches back through ``restated_quarter_id``.

    Both ``f.avg`` handlers use ``periods=f.quarter_number + 1``, i.e. the
    current quarter plus every YTD quarter back to the prior year-end. So:

      * (Y, Q1..Q3) restatement → forward window = same-year (Q+1..Q4)
      * (Y, Q4) restatement → forward window = next-year (Q1..Q4), since
        Q4 is the "prior year-end" balance every Y+1 quarter averages in.

    The contract test ``TestAvgPattern`` keeps this assumption load-bearing:
    if a future handler introduces a different ``periods`` expression, the
    contract test will fail before this helper is silently wrong.
    """
    year, quarter = parse_quarter_id(restated_quarter_id)
    if quarter < 4:
        return [quarter_id(year, q) for q in range(quarter + 1, 5)]
    return [quarter_id(year + 1, q) for q in range(1, 5)]


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
        if affected:
            session.execute(
                update(Ratio)
                .where(
                    Ratio.cert == cert,
                    Ratio.quarter_id == quarter_id,
                    Ratio.ratio_id.in_(affected),
                )
                .values(data_quality="partial")
            )
        # Forward flip: ratios that read this field via f.avg(...) also
        # need refresh at the YTD-affected downstream quarters. Issued as
        # a second UPDATE — not folded into the first — so the WHERE
        # clauses stay narrow (current-quarter flip touches direct readers
        # too; forward flip is f.avg consumers only).
        avg_consumers = _avg_consumers_by_field().get(field_code)
        if not avg_consumers:
            return
        forward_qids = _ytd_forward_quarters(quarter_id)
        if not forward_qids:
            return
        session.execute(
            update(Ratio)
            .where(
                Ratio.cert == cert,
                Ratio.quarter_id.in_(forward_qids),
                Ratio.ratio_id.in_(avg_consumers),
            )
            .values(data_quality="partial")
        )

    return _callback
