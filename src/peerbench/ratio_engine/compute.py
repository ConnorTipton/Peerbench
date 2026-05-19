"""Ratio compute orchestration.

The dispatcher pulls a FactView for one bank-quarter, walks ratios in
topological order (so dependent ratios like `nis` see their parents'
values), checks suppression, dispatches to the handler, and classifies the
result as Ok / Partial / Suppressed. Persistence to the `ratios` table
lives in the CLI layer — this module stays pure.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from decimal import Decimal, DivisionByZero, InvalidOperation

from sqlalchemy import select
from sqlalchemy.orm import Session

from peerbench.db.models import Fact, RatioDef
from peerbench.quarters import parse_quarter_id, previous_quarter, quarter_id
from peerbench.ratio_engine.fact_view import FactView, MissingFieldError
from peerbench.ratio_engine.registry import RegisteredHandler, get_handler, registered_handlers
from peerbench.ratio_engine.suppression import (
    PartialResult,
    SuppressedResult,
    should_suppress,
)


@dataclass(frozen=True)
class OkResult:
    value: Decimal


RatioResult = OkResult | PartialResult | SuppressedResult


def data_quality_for(result: RatioResult) -> str:
    if isinstance(result, OkResult):
        return "ok"
    if isinstance(result, PartialResult):
        return "partial"
    if isinstance(result, SuppressedResult):
        return "suppressed"
    msg = f"unknown ratio result type: {type(result).__name__}"
    raise TypeError(msg)


# Ratios that depend on other ratios, not just raw facts. Day 3 onward
# wires these into the topological resolver. `nis` reads yield_ea and
# cost_funds outputs (plan §5 deferred). Empty for everything else.
RATIO_DEPENDENCIES: dict[str, frozenset[str]] = {
    "nis": frozenset({"yield_ea", "cost_funds"}),
}


def topological_order(ratio_ids: Iterable[str]) -> Iterator[str]:
    """Yield ratio_ids such that any dependent is yielded after its dependencies."""
    remaining = set(ratio_ids)
    while remaining:
        progressed = False
        for rid in list(remaining):
            deps = RATIO_DEPENDENCIES.get(rid, frozenset())
            unmet = deps & remaining
            if not unmet:
                yield rid
                remaining.discard(rid)
                progressed = True
        if not progressed:
            msg = f"ratio dependency cycle or unknown dep among: {sorted(remaining)}"
            raise RuntimeError(msg)


def _period_quarter_ids(target: str, periods: int) -> list[str]:
    """[target, target-1, target-2, ..., target-(periods-1)], newest first."""
    year, q = parse_quarter_id(target)
    out: list[str] = []
    for _ in range(periods):
        out.append(quarter_id(year, q))
        year, q = previous_quarter(year, q)
    return out


def load_fact_view(
    session: Session,
    cert: int,
    target_quarter_id: str,
    periods: int = 5,
) -> FactView:
    """Pull facts for `periods` quarters into a FactView, newest first.

    For ratios that need 5-period YTD averaging (NIM, ROA, ROE, etc.) we
    need the target quarter and the 4 preceding ones — total 5. Missing
    quarters become empty dicts, so the handler's FactView.avg() raises
    MissingFieldError, which the dispatcher turns into PartialResult.
    """
    qids = _period_quarter_ids(target_quarter_id, periods)
    rows = session.scalars(select(Fact).where(Fact.cert == cert, Fact.quarter_id.in_(qids))).all()
    by_quarter: dict[str, dict[str, Decimal | None]] = {q: {} for q in qids}
    for row in rows:
        by_quarter[row.quarter_id][row.field_code] = row.value
    _, qnum = parse_quarter_id(target_quarter_id)
    return FactView(
        cert=cert,
        quarter_id=target_quarter_id,
        quarter_number=qnum,
        facts_by_period=tuple(by_quarter[q] for q in qids),
    )


def compute_ratio(
    ratio_def: RatioDef,
    fact_view: FactView,
    handler: RegisteredHandler | None = None,
) -> RatioResult:
    """Suppression check, then handler dispatch, then classify."""
    suppressed = should_suppress(ratio_def, fact_view)
    if suppressed is not None:
        return suppressed
    h = handler or get_handler(ratio_def.ratio_id)
    if h is None:
        return PartialResult(value=None, missing_fields=("__no_handler__",))
    try:
        value = h.func(fact_view)
    except MissingFieldError as e:
        return PartialResult(value=None, missing_fields=(str(e),))
    except NotImplementedError:
        return PartialResult(value=None, missing_fields=("__not_implemented__",))
    except (DivisionByZero, InvalidOperation) as e:
        return PartialResult(value=None, missing_fields=(f"__arith__:{e}",))
    return OkResult(value=value)


def compute_all_for_bank_quarter(
    ratio_defs: list[RatioDef],
    fact_view: FactView,
) -> dict[str, RatioResult]:
    """Walk every ratio in topological order, return a {ratio_id: result} map.

    Dependent ratios (only `nis` for now) see prior results via a closure
    so they can read computed dependencies. Day 3 keeps this simple — the
    `nis` handler reads yield_ea and cost_funds directly when its turn
    comes.
    """
    defs_by_id = {r.ratio_id: r for r in ratio_defs}
    handlers = registered_handlers()
    results: dict[str, RatioResult] = {}
    for rid in topological_order(defs_by_id.keys()):
        rdef = defs_by_id[rid]
        results[rid] = compute_ratio(rdef, fact_view, handlers.get(rid))
    return results
