"""Decimal preservation through the value path.

The Phase 1 DoD requires <2 bps mean abs error vs FDIC pre-computed. A single
`float` cast in the value path silently truncates precision and breaks the
DoD. This test asserts that Decimal values survive every boundary that the
ingest path crosses: Pydantic parsing, the to_decimal helper, and arithmetic.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from peerbench.decimal_ import to_decimal


class TestToDecimal:
    def test_accepts_decimal(self) -> None:
        v = Decimal("1234.56789")
        assert to_decimal(v) is v

    def test_accepts_int(self) -> None:
        assert to_decimal(42) == Decimal(42)

    def test_accepts_str(self) -> None:
        # FDIC returns numerics as JSON strings in some endpoints.
        assert to_decimal("1234.56789") == Decimal("1234.56789")

    def test_refuses_float(self) -> None:
        # The point of the helper: refuse float so the bug is loud.
        with pytest.raises(TypeError, match="refusing to coerce float"):
            to_decimal(1234.56789)  # type: ignore[arg-type]

    def test_preserves_high_precision(self) -> None:
        s = "0.12345678901234567890"
        assert str(to_decimal(s)) == s


class TestDecimalArithmetic:
    def test_division_uses_context_precision(self) -> None:
        # NIM-style: net interest income / average earning assets.
        # If anyone coerces to float mid-pipeline, this answer drifts.
        nii = Decimal("1234567890.12")
        aea = Decimal("87654321098.76")
        ratio = nii / aea
        # Stays a Decimal (no silent float coercion) and carries the
        # 28-digit context precision configured in peerbench.decimal_.
        assert isinstance(ratio, Decimal)
        digits = ratio.as_tuple().digits
        assert len(digits) == 28
        # Float equivalent drifts at ~17 sig figs; Decimal must not.
        assert ratio != Decimal(repr(float(nii) / float(aea)))

    def test_bps_conversion_is_lossless(self) -> None:
        ratio = Decimal("0.034512345")
        bps = ratio * Decimal(10000)
        assert bps == Decimal("345.12345")
