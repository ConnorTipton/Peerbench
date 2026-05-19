"""Decimal precision discipline for the value path.

Phase 1 DoD requires mean abs error < 2 bps vs FDIC pre-computed. Any `float`
in the value path breaks that. This module is the *only* place that touches
the global Decimal context — import-time call to `configure_decimal()` from
`peerbench.__init__` makes the setting cover any code path that imports
anything from `peerbench`.
"""

from decimal import ROUND_HALF_EVEN, Decimal, getcontext

PRECISION = 28


def configure_decimal() -> None:
    ctx = getcontext()
    ctx.prec = PRECISION
    ctx.rounding = ROUND_HALF_EVEN


def to_decimal(value: object) -> Decimal:
    """Convert a JSON-decoded numeric (int, str, Decimal) to Decimal.

    Refuses float on purpose — float input means somebody parsed JSON without
    a Decimal hook, and silent coercion would hide the bug.
    """
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, str):
        return Decimal(value)
    msg = f"refusing to coerce {type(value).__name__} to Decimal: {value!r}"
    raise TypeError(msg)
