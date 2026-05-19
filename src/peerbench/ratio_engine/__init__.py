"""Ratio computation engine.

Per-ratio Python handler registry (see plan §5). `ratio_defs` rows hold the
human-readable formula; handlers in `peerbench.ratio_engine.handlers` are
the source of truth for execution. The contract test in
`tests/contract/test_ratio_registry.py` keeps them in 1:1 correspondence.
"""

# Importing handlers triggers @ratio decoration → registry population.
from peerbench.ratio_engine import handlers as _handlers  # noqa: F401
from peerbench.ratio_engine.fact_view import FactView, MissingFieldError
from peerbench.ratio_engine.registry import (
    RegisteredHandler,
    ratio,
    registered_handlers,
)
from peerbench.ratio_engine.suppression import (
    PartialResult,
    SuppressedResult,
    should_suppress,
)

__all__ = [
    "FactView",
    "MissingFieldError",
    "PartialResult",
    "RegisteredHandler",
    "SuppressedResult",
    "ratio",
    "registered_handlers",
    "should_suppress",
]
