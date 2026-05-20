"""Unit tests for the validation harness.

Pure-function tests for the math + rendering. The DB-touching
`compare_to_fdic` is covered by the live `peerbench validate` smoke run
in the Day 4 verification checklist — building Postgres-backed fixtures
just for one read-only function is out of scope.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from peerbench.validate import (
    Comparison,
    ExclusionStats,
    compute_bp_diff,
    evaluate_gate,
    format_table,
    write_snapshot,
)


def _cmp(bp: str, ratio: str = "nim", cert: int = 4063) -> Comparison:
    return Comparison(
        cert=cert,
        quarter_id="2025-Q4",
        ratio_id=ratio,
        our_value=Decimal("0.0342"),
        fdic_value=Decimal("0.0342"),
        bp_diff=Decimal(bp),
    )


def _excl(missing_ratio_row: int = 0) -> ExclusionStats:
    return ExclusionStats(
        no_fdic_code=0,
        not_ok_quality=0,
        missing_fdic_fact=0,
        missing_ratio_row=missing_ratio_row,
    )


class TestEvaluateGate:
    def test_pass_under_thresholds(self) -> None:
        verdict, mean, mx = evaluate_gate([_cmp("0.50"), _cmp("1.00")], _excl())
        assert verdict == "PASS"
        assert mean == Decimal("0.75")
        assert mx == Decimal("1.00")

    def test_fail_on_no_comparisons(self) -> None:
        verdict, mean, mx = evaluate_gate([], _excl())
        assert verdict.startswith("FAIL")
        assert "no comparisons" in verdict
        assert mean == Decimal(0)
        assert mx == Decimal(0)

    def test_fail_on_mean_breach(self) -> None:
        # mean = 2.5, exceeds DOD_MEAN_BPS (2)
        verdict, _, _ = evaluate_gate([_cmp("2.00"), _cmp("3.00")], _excl())
        assert verdict.startswith("FAIL")
        assert "mean" in verdict

    def test_fail_on_max_breach(self) -> None:
        # max = 5, exceeds DOD_MAX_BPS (5) — strict >= check
        verdict, _, _ = evaluate_gate([_cmp("0.50"), _cmp("5.00")], _excl())
        assert verdict.startswith("FAIL")
        assert "max" in verdict

    def test_fail_on_missing_ratio_row(self) -> None:
        # All bps in range, but 1 expected row is missing — must fail.
        verdict, _, _ = evaluate_gate([_cmp("0.50")], _excl(missing_ratio_row=1))
        assert verdict.startswith("FAIL")
        assert "missing" in verdict

    def test_fail_reasons_concatenated(self) -> None:
        # Two breach reasons at once should both appear in the verdict.
        verdict, _, _ = evaluate_gate([_cmp("3.00"), _cmp("6.00")], _excl(missing_ratio_row=2))
        assert verdict.startswith("FAIL")
        assert "mean" in verdict
        assert "max" in verdict
        assert "missing" in verdict


class TestExclusionStatsDefault:
    def test_missing_ratio_row_defaults_to_zero(self) -> None:
        # Old 3-arg call sites stay green; new field defaults to 0.
        e = ExclusionStats(no_fdic_code=1, not_ok_quality=2, missing_fdic_fact=3)
        assert e.missing_ratio_row == 0


class TestComputeBpDiff:
    def test_fraction_vs_percent_scaling(self) -> None:
        # our = 0.0250 (2.50%), fdic = 2.55% — diff = 0.0005 fraction = 5 bps.
        assert compute_bp_diff(Decimal("0.0250"), Decimal("2.55")) == Decimal(5)

    def test_zero_diff(self) -> None:
        assert compute_bp_diff(Decimal("0.0342"), Decimal("3.42")) == Decimal(0)

    def test_absolute_value(self) -> None:
        # our 3.40% > fdic 3.42% → still positive 2 bps
        assert compute_bp_diff(Decimal("0.0340"), Decimal("3.42")) == Decimal(2)

    def test_decimal_clean_no_float_drift(self) -> None:
        # Sanity: a value that would float-drift with binary fp stays exact.
        result = compute_bp_diff(Decimal("0.123456"), Decimal("12.3457"))
        # 12.3457% = 0.123457 fraction. diff = 0.000001. bps = 0.01.
        assert result == Decimal("0.01")


class TestFormatTable:
    def test_empty(self) -> None:
        assert format_table([]) == "_no comparisons_"

    def test_grouped_by_ratio_id(self) -> None:
        c1 = Comparison(
            cert=4063,
            quarter_id="2025-Q4",
            ratio_id="nim",
            our_value=Decimal("0.0342"),
            fdic_value=Decimal("0.0342"),
            bp_diff=Decimal("0.50"),
        )
        c2 = Comparison(
            cert=4214,
            quarter_id="2025-Q4",
            ratio_id="nim",
            our_value=Decimal("0.0305"),
            fdic_value=Decimal("0.0305"),
            bp_diff=Decimal("1.50"),
        )
        c3 = Comparison(
            cert=4063,
            quarter_id="2025-Q4",
            ratio_id="roa",
            our_value=Decimal("0.0125"),
            fdic_value=Decimal("0.0125"),
            bp_diff=Decimal("0.10"),
        )
        out = format_table([c1, c2, c3])
        # alphabetical row order: nim, roa
        assert "| nim | 2 | 1.00 | 1.50 | 1.50 |" in out
        assert "| roa | 1 | 0.10 | 0.10 | 0.10 |" in out


class TestWriteSnapshot:
    def test_pass_verdict(self, tmp_path: Path) -> None:
        c = Comparison(
            cert=4063,
            quarter_id="2025-Q4",
            ratio_id="nim",
            our_value=Decimal("0.0342"),
            fdic_value=Decimal("0.0342"),
            bp_diff=Decimal("0.50"),
        )
        path = tmp_path / "snap.md"
        gate = write_snapshot(
            [c],
            ExclusionStats(no_fdic_code=0, not_ok_quality=0, missing_fdic_fact=0),
            path,
            certs=[4063],
            quarter_ids=["2025-Q4"],
        )
        assert gate == "PASS"
        body = path.read_text()
        assert "**PASS**" in body
        assert "| nim |" in body

    def test_fail_verdict_on_breach(self, tmp_path: Path) -> None:
        c = Comparison(
            cert=4063,
            quarter_id="2025-Q4",
            ratio_id="nim",
            our_value=Decimal("0.0342"),
            fdic_value=Decimal("0.0342"),
            bp_diff=Decimal("10.00"),  # exceeds DoD max of 5
        )
        path = tmp_path / "snap.md"
        gate = write_snapshot(
            [c],
            ExclusionStats(no_fdic_code=0, not_ok_quality=0, missing_fdic_fact=0),
            path,
            certs=[4063],
            quarter_ids=["2025-Q4"],
        )
        assert gate.startswith("FAIL")
        assert "max" in gate

    def test_no_comparisons(self, tmp_path: Path) -> None:
        path = tmp_path / "snap.md"
        gate = write_snapshot(
            [],
            ExclusionStats(no_fdic_code=30, not_ok_quality=0, missing_fdic_fact=0),
            path,
            certs=[4063],
            quarter_ids=["2025-Q4"],
        )
        assert gate.startswith("FAIL")

    def test_snapshot_body_lists_missing_ratio_row(self, tmp_path: Path) -> None:
        c = Comparison(
            cert=4063,
            quarter_id="2025-Q4",
            ratio_id="nim",
            our_value=Decimal("0.0342"),
            fdic_value=Decimal("0.0342"),
            bp_diff=Decimal("0.50"),
        )
        path = tmp_path / "snap.md"
        gate = write_snapshot(
            [c],
            ExclusionStats(
                no_fdic_code=0,
                not_ok_quality=0,
                missing_fdic_fact=0,
                missing_ratio_row=7,
            ),
            path,
            certs=[4063],
            quarter_ids=["2025-Q4"],
        )
        body = path.read_text()
        assert "Expected ratios row missing" in body
        assert ": 7" in body
        # Missing rows must also fail the gate even when bps are clean.
        assert gate.startswith("FAIL")
