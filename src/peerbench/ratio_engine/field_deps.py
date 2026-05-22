"""Field-dependency extraction for the handler registry.

Each handler body references zero or more FFIEC field codes (e.g. ``f["NIM"]``,
``f.avg("DEPI", periods=...)``). The restatement detector needs that mapping to
scope its work: when a single field is restated for a bank/quarter, only the
ratios that read that field should be marked. Without this mapping, both the
ingest callback (``ingest/quality_log.py``) and the dashboard (``ratio-matrix``)
fall back to a coarse ``(cert, quarter)`` scope, which over-marks unrelated
cells.

The handlers themselves remain the single source of truth for both formulas and
dependencies — we just expose the dep edges via AST walk instead of forcing
authors to repeat themselves in a decorator argument.

Patterns recognised (and the only ones currently used in the codebase):

  * ``f["FIELD"]``
  * ``f.get("FIELD", ...)`` / ``f.get("FIELD", default=...)``
  * ``f.avg("FIELD", periods=...)``
  * ``f.current.get("FIELD", ...)``

For ratios that delegate to module-level helpers (e.g. ``nis`` calls
``_yield_ea`` and ``_cost_funds`` in ``yields.py``), the extractor recurses into
the helper's source. For ratios that read other ratios' outputs (only ``nis``
today, declared in ``RATIO_DEPENDENCIES``), the transitive closure is taken.

Suppression edges are unioned in last: a ratio with ``suppress_when={"cblr":
true}`` reads ``CBLRIND`` indirectly via ``should_suppress``, not from its
handler body. Without this, a ``CBLRIND`` restatement would skip the partial
flip for ``cet1``/``tier1_rbc``/``total_rbc`` even though their data_quality
(``ok`` ↔ ``suppressed``) depends on it. The mapping lives in
``suppression.SUPPRESS_KEY_FIELDS`` so handler authors update it alongside any
new suppression branch.
"""

from __future__ import annotations

import ast
import inspect
import textwrap
from collections.abc import Callable
from types import ModuleType

from peerbench.ratio_defs_io import load_ratio_defs
from peerbench.ratio_engine.compute import RATIO_DEPENDENCIES
from peerbench.ratio_engine.registry import registered_handlers
from peerbench.ratio_engine.suppression import SUPPRESS_KEY_FIELDS


def _extract_from_function(func: Callable[..., object]) -> frozenset[str]:
    """Walk one function's AST, returning field codes it reads off ``f``.

    Recurses into module-level helpers the function calls so that ratios which
    delegate (e.g. ``compute_nis -> _yield_ea``) still surface their deps.
    """
    try:
        source = inspect.getsource(func)
    except (OSError, TypeError):
        return frozenset()
    tree = ast.parse(textwrap.dedent(source))
    if not tree.body or not isinstance(tree.body[0], ast.FunctionDef):
        return frozenset()
    func_def = tree.body[0]
    module = inspect.getmodule(func)
    fields: set[str] = set()
    visited_helpers: set[str] = {func_def.name}
    _visit(func_def, module, fields, visited_helpers)
    return frozenset(fields)


def _extract_avg_fields_from_function(func: Callable[..., object]) -> frozenset[str]:
    """Walk one function's AST, returning ONLY field codes read via ``f.avg(...)``.

    Same helper-recursion contract as ``_extract_from_function`` — needed
    because ``compute_nis`` delegates to ``_cost_funds`` which is where the
    ``f.avg("DEPI", ...)`` call lives.
    """
    try:
        source = inspect.getsource(func)
    except (OSError, TypeError):
        return frozenset()
    tree = ast.parse(textwrap.dedent(source))
    if not tree.body or not isinstance(tree.body[0], ast.FunctionDef):
        return frozenset()
    func_def = tree.body[0]
    module = inspect.getmodule(func)
    fields: set[str] = set()
    visited_helpers: set[str] = {func_def.name}
    _visit_avg(func_def, module, fields, visited_helpers)
    return frozenset(fields)


def _visit(
    node: ast.AST,
    module: ModuleType | None,
    fields: set[str],
    visited_helpers: set[str],
) -> None:
    for child in ast.walk(node):
        if isinstance(child, ast.Subscript):
            # f["FIELD"]
            if (
                isinstance(child.value, ast.Name)
                and child.value.id == "f"
                and isinstance(child.slice, ast.Constant)
                and isinstance(child.slice.value, str)
            ):
                fields.add(child.slice.value)
        elif isinstance(child, ast.Call):
            _handle_call(child, module, fields, visited_helpers)


def _handle_call(
    call: ast.Call,
    module: ModuleType | None,
    fields: set[str],
    visited_helpers: set[str],
) -> None:
    func = call.func
    # f.get("FIELD", ...) / f.avg("FIELD", ...)
    if (
        isinstance(func, ast.Attribute)
        and isinstance(func.value, ast.Name)
        and func.value.id == "f"
        and func.attr in {"get", "avg"}
        and call.args
        and isinstance(call.args[0], ast.Constant)
        and isinstance(call.args[0].value, str)
    ):
        fields.add(call.args[0].value)
        return
    # f.current.get("FIELD", ...)
    if (
        isinstance(func, ast.Attribute)
        and func.attr == "get"
        and isinstance(func.value, ast.Attribute)
        and func.value.attr == "current"
        and isinstance(func.value.value, ast.Name)
        and func.value.value.id == "f"
        and call.args
        and isinstance(call.args[0], ast.Constant)
        and isinstance(call.args[0].value, str)
    ):
        fields.add(call.args[0].value)
        return
    # Local helper call (e.g. _yield_ea(f)): resolve in the same module.
    if isinstance(func, ast.Name) and module is not None and func.id not in visited_helpers:
        helper = getattr(module, func.id, None)
        if inspect.isfunction(helper) and inspect.getmodule(helper) is module:
            visited_helpers.add(func.id)
            fields.update(_extract_from_function(helper))


def _visit_avg(
    node: ast.AST,
    module: ModuleType | None,
    fields: set[str],
    visited_helpers: set[str],
) -> None:
    """AST visitor for ``f.avg("FIELD", ...)`` calls only.

    Skips ``f["FIELD"]``, ``f.get(...)``, and ``f.current.get(...)`` — the
    cross-quarter recompute trigger fires only on YTD-averaged consumers,
    not direct same-quarter reads.
    """
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        func = child.func
        if (
            isinstance(func, ast.Attribute)
            and isinstance(func.value, ast.Name)
            and func.value.id == "f"
            and func.attr == "avg"
            and child.args
            and isinstance(child.args[0], ast.Constant)
            and isinstance(child.args[0].value, str)
        ):
            fields.add(child.args[0].value)
            continue
        # Recurse into local helper calls so e.g. ``compute_nis -> _cost_funds``
        # surfaces the DEPI avg dep at the nis ratio's level.
        if isinstance(func, ast.Name) and module is not None and func.id not in visited_helpers:
            helper = getattr(module, func.id, None)
            if inspect.isfunction(helper) and inspect.getmodule(helper) is module:
                visited_helpers.add(func.id)
                fields.update(_extract_avg_fields_from_function(helper))


def extract_field_deps() -> dict[str, frozenset[str]]:
    """Return ``{ratio_id: frozenset(field_code)}`` for every registered handler.

    Three sources are unioned per ratio:

      1. Direct AST reads from the handler body (and any helpers it calls in
         the same module).
      2. Transitive deps from ``RATIO_DEPENDENCIES`` (today only ``nis ->
         {yield_ea, cost_funds}``), so a restatement on ``INTINC`` (which feeds
         ``yield_ea``) also marks ``nis``.
      3. Suppression deps from ``SUPPRESS_KEY_FIELDS`` for any ratio whose
         ``ratio_defs.suppress_when`` opts into a suppression branch. Without
         these, a ``CBLRIND`` restatement skips ``cet1``/``tier1_rbc``/
         ``total_rbc`` even though those cells transition between ``ok`` and
         ``suppressed`` on the flag's value.

    Raises ``RuntimeError`` if the registry is empty (handlers not yet imported)
    or if ``RATIO_DEPENDENCIES`` has a cycle.
    """
    handlers = registered_handlers()
    if not handlers:
        msg = "registered_handlers() is empty — import peerbench.ratio_engine first"
        raise RuntimeError(msg)

    suppress_by_ratio: dict[str, frozenset[str]] = {}
    for row in load_ratio_defs():
        keys = row.suppress_when or {}
        fields: set[str] = set()
        for key, enabled in keys.items():
            if not enabled:
                continue
            fields.update(SUPPRESS_KEY_FIELDS.get(key, ()))
        if fields:
            suppress_by_ratio[row.ratio_id] = frozenset(fields)

    direct: dict[str, frozenset[str]] = {
        rid: _extract_from_function(h.func) | suppress_by_ratio.get(rid, frozenset())
        for rid, h in handlers.items()
    }

    resolved: dict[str, frozenset[str]] = {}

    def resolve(rid: str, stack: tuple[str, ...]) -> frozenset[str]:
        if rid in resolved:
            return resolved[rid]
        if rid in stack:
            cycle = " -> ".join((*stack, rid))
            msg = f"ratio dependency cycle: {cycle}"
            raise RuntimeError(msg)
        out: set[str] = set(direct.get(rid, frozenset()))
        for parent in RATIO_DEPENDENCIES.get(rid, frozenset()):
            out |= resolve(parent, (*stack, rid))
        resolved[rid] = frozenset(out)
        return resolved[rid]

    for rid in direct:
        resolve(rid, ())
    return resolved


def extract_avg_field_deps() -> dict[str, frozenset[str]]:
    """Return ``{ratio_id: frozenset(field_code)}`` for fields read via ``f.avg(...)``.

    Strict subset of :func:`extract_field_deps` — only ``f.avg(...)`` reads,
    not direct ``f["FIELD"]`` or ``f.get(...)``. The restatement detector
    uses this to decide which downstream quarters to mark stale when a
    fact diff lands:

      * ``nco_ratio`` averages ``LNLSGR`` over ``quarter_number + 1`` periods,
        so a Q2 LNLSGR restatement also invalidates Q3 and Q4 ``nco_ratio``.
      * ``cost_funds`` averages ``DEPI`` likewise.
      * ``nis`` reads ``cost_funds`` via ``RATIO_DEPENDENCIES`` — the transitive
        closure surfaces ``DEPI`` on ``nis``'s avg-dep set so a DEPI
        restatement marks the forward ``nis`` rows stale too.

    Suppression edges (``CBLRIND`` etc.) are NOT unioned in here — the
    suppression check runs on the *current* quarter's facts only, not on
    averaged inputs, so a CBLRIND restatement does not propagate forward
    even for ratios whose ``cet1`` / ``tier1_rbc`` / ``total_rbc`` output
    depends on the suppression flag.

    Raises ``RuntimeError`` if the registry is empty or ``RATIO_DEPENDENCIES``
    has a cycle (matches :func:`extract_field_deps`'s contract).
    """
    handlers = registered_handlers()
    if not handlers:
        msg = "registered_handlers() is empty — import peerbench.ratio_engine first"
        raise RuntimeError(msg)

    direct: dict[str, frozenset[str]] = {
        rid: _extract_avg_fields_from_function(h.func) for rid, h in handlers.items()
    }

    resolved: dict[str, frozenset[str]] = {}

    def resolve(rid: str, stack: tuple[str, ...]) -> frozenset[str]:
        if rid in resolved:
            return resolved[rid]
        if rid in stack:
            cycle = " -> ".join((*stack, rid))
            msg = f"ratio dependency cycle: {cycle}"
            raise RuntimeError(msg)
        out: set[str] = set(direct.get(rid, frozenset()))
        for parent in RATIO_DEPENDENCIES.get(rid, frozenset()):
            out |= resolve(parent, (*stack, rid))
        resolved[rid] = frozenset(out)
        return resolved[rid]

    for rid in direct:
        resolve(rid, ())
    return resolved
