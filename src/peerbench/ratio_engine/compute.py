"""Topological resolver for dependent ratios.

Most ratios depend only on raw facts; a few depend on other computed ratios
(e.g. `nis` = `yield_ea` - `cost_funds`). Day 2 ships the resolver skeleton;
Day 3 fills in the handler bodies and decides whether `nis` stays a row in
the `ratios` table or moves to a SQL view (plan §5 deferred question).
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator

# Ratios that depend on other ratios, not just raw facts. Day 2 declares
# the edges; Day 3 wires them into the compute order.
RATIO_DEPENDENCIES: dict[str, frozenset[str]] = {
    "nis": frozenset({"yield_ea", "cost_funds"}),
}


def topological_order(ratio_ids: Iterable[str]) -> Iterator[str]:
    """Yield ratio_ids such that any dependent is yielded after its dependencies."""
    remaining = set(ratio_ids)
    emitted: set[str] = set()
    # Bounded by len(remaining) iterations: each pass must emit ≥1 or fail.
    while remaining:
        progressed = False
        for rid in list(remaining):
            deps = RATIO_DEPENDENCIES.get(rid, frozenset())
            unmet = deps & remaining
            if not unmet:
                yield rid
                emitted.add(rid)
                remaining.discard(rid)
                progressed = True
        if not progressed:
            msg = f"ratio dependency cycle or unknown dep among: {sorted(remaining)}"
            raise RuntimeError(msg)
