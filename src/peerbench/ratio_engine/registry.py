"""@ratio decorator and the global handler registry.

Each handler is paired with a `version` string (e.g. 'v1') and an AST-hash of
its function body (decorators stripped). The pairing is the load-bearing
piece for the version-pinning workflow:

    - Edit a handler body → AST hash changes.
    - The contract test compares the registry's (version, ast_hash) pair
      against a snapshot file; mismatches fail CI.
    - To intentionally change a handler, bump both the @ratio(version=...)
      argument and the corresponding row's formula_version in ratios.csv;
      the seed CLI also enqueues a backfill of stale rows.

This module never imports handler modules itself — that's the job of
`peerbench.ratio_engine.handlers.__init__`. Importing this module before
the handlers package will leave the registry empty.
"""

from __future__ import annotations

import ast
import hashlib
import inspect
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from peerbench.ratio_engine.fact_view import FactView

HandlerFunc = Callable[["FactView"], Decimal]


@dataclass(frozen=True)
class RegisteredHandler:
    ratio_id: str
    version: str
    ast_hash: str
    func: HandlerFunc


_REGISTRY: dict[str, RegisteredHandler] = {}


def _compute_ast_hash(func: HandlerFunc) -> str:
    """Hash the function body (decorators + signature stripped of versions)."""
    try:
        source = inspect.getsource(func)
    except OSError:
        # Dynamically-defined functions (e.g. lambdas in tests) have no source.
        return "no-source"
    source = inspect.cleandoc(source) if not source.lstrip().startswith("@") else source
    # Re-indent so ast.parse accepts function definitions extracted from classes.
    source = "\n".join(line for line in source.splitlines())
    tree = ast.parse(source)
    if not tree.body or not isinstance(tree.body[0], ast.FunctionDef):
        return "not-a-function"
    func_def = tree.body[0]
    # Strip decorators so version bumps in @ratio(...) don't shift the hash.
    func_def.decorator_list = []
    dump = ast.dump(func_def, annotate_fields=False, include_attributes=False)
    return hashlib.sha256(dump.encode()).hexdigest()[:16]


def ratio(ratio_id: str, *, version: str = "v1") -> Callable[[HandlerFunc], HandlerFunc]:
    """Register a handler for `ratio_id`. Raises on duplicate registration."""

    def decorator(func: HandlerFunc) -> HandlerFunc:
        if ratio_id in _REGISTRY:
            existing = _REGISTRY[ratio_id]
            msg = (
                f"ratio_id {ratio_id!r} already registered by "
                f"{existing.func.__module__}.{existing.func.__name__}"
            )
            raise RuntimeError(msg)
        _REGISTRY[ratio_id] = RegisteredHandler(
            ratio_id=ratio_id,
            version=version,
            ast_hash=_compute_ast_hash(func),
            func=func,
        )
        return func

    return decorator


def registered_handlers() -> dict[str, RegisteredHandler]:
    """Snapshot of the registry. Returns a copy so callers can't mutate it."""
    return dict(_REGISTRY)


def get_handler(ratio_id: str) -> RegisteredHandler | None:
    return _REGISTRY.get(ratio_id)
