"""Validation harness: compare computed ratios against FDIC pre-computed.

Pulls `(cert, quarter_id, ratio_id, value)` from the `ratios` table where
`data_quality='ok'`, looks up the matching FDIC pre-computed code via
`ratio_defs.fdic_precomputed_code`, fetches that fact's value, and computes
an absolute basis-point diff.

FDIC pre-computed ratios are reported as percentages (e.g. NIMY = 3.42);
ours are stored as fractions (e.g. nim = 0.0342). The scaling is the
single load-bearing arithmetic in this module — all other transforms are
report-shaping.

Used by Day 4 sign-off and the future Phase 3 daily-cron deploy guard.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from peerbench.db.models import Fact, Ratio, RatioDef

ONE_HUNDRED = Decimal(100)
ONE_E4 = Decimal(10000)
DOD_MEAN_BPS = Decimal(2)
DOD_MAX_BPS = Decimal(5)


@dataclass(frozen=True)
class Comparison:
    cert: int
    quarter_id: str
    ratio_id: str
    our_value: Decimal
    fdic_value: Decimal  # already in fraction form
    bp_diff: Decimal


@dataclass(frozen=True)
class ExclusionStats:
    """Counts of ratios that did not produce a comparison."""

    no_fdic_code: int  # ratio_def has no fdic_precomputed_code
    not_ok_quality: int  # our ratio row exists but data_quality != 'ok'
    missing_fdic_fact: int  # ratio mapped to a code but the fact row is missing/None


def compute_bp_diff(our: Decimal, fdic_pct: Decimal) -> Decimal:
    """Absolute basis-point diff between our fraction and FDIC's percent.

    Pure function, no session — easy to unit test. FDIC inputs are scaled
    from percent to fraction (divide by 100), then `|our - fdic_frac| * 1e4`.
    """
    fdic_frac = fdic_pct / ONE_HUNDRED
    return abs(our - fdic_frac) * ONE_E4


def compare_to_fdic(
    session: Session,
    certs: list[int],
    quarter_ids: list[str],
) -> tuple[list[Comparison], ExclusionStats]:
    """Return per-(cert, quarter, ratio) comparisons + exclusion counts.

    Only `data_quality='ok'` ratios participate. Stale ('partial') or
    suppressed ratios are excluded by design — see Risk #5 in the Day 4
    plan. The ExclusionStats lets callers spot silent gaps.
    """
    rdefs: dict[str, str | None] = {
        r.ratio_id: r.fdic_precomputed_code for r in session.scalars(select(RatioDef)).all()
    }

    all_rows = list(
        session.scalars(
            select(Ratio).where(
                Ratio.cert.in_(certs),
                Ratio.quarter_id.in_(quarter_ids),
            )
        ).all()
    )

    comparisons: list[Comparison] = []
    no_fdic_code = 0
    not_ok_quality = 0
    missing_fdic_fact = 0

    for row in all_rows:
        code = rdefs.get(row.ratio_id)
        if not code:
            no_fdic_code += 1
            continue
        if row.data_quality != "ok" or row.value is None:
            not_ok_quality += 1
            continue
        fact = session.get(Fact, (row.cert, row.quarter_id, code))
        if fact is None or fact.value is None:
            missing_fdic_fact += 1
            continue
        comparisons.append(
            Comparison(
                cert=row.cert,
                quarter_id=row.quarter_id,
                ratio_id=row.ratio_id,
                our_value=row.value,
                fdic_value=fact.value / ONE_HUNDRED,
                bp_diff=compute_bp_diff(row.value, fact.value),
            )
        )

    return comparisons, ExclusionStats(
        no_fdic_code=no_fdic_code,
        not_ok_quality=not_ok_quality,
        missing_fdic_fact=missing_fdic_fact,
    )


def _percentile_nearest_rank(values: list[Decimal], pct: Decimal) -> Decimal:
    sorted_vals = sorted(values)
    if not sorted_vals:
        return Decimal(0)
    rank = (pct * Decimal(len(sorted_vals))).to_integral_value()
    idx = min(int(rank), len(sorted_vals) - 1)
    return sorted_vals[idx]


def format_table(comparisons: list[Comparison]) -> str:
    """Markdown table grouped by ratio_id with N / mean / max / p95 bp diffs."""
    if not comparisons:
        return "_no comparisons_"

    groups: dict[str, list[Decimal]] = {}
    for c in comparisons:
        groups.setdefault(c.ratio_id, []).append(c.bp_diff)

    lines = [
        "| Ratio | N | Mean bp | Max bp | p95 bp |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for rid in sorted(groups):
        diffs = groups[rid]
        n = len(diffs)
        mean = sum(diffs, Decimal(0)) / Decimal(n)
        mx = max(diffs)
        p95 = _percentile_nearest_rank(diffs, Decimal("0.95"))
        lines.append(f"| {rid} | {n} | {mean:.2f} | {mx:.2f} | {p95:.2f} |")
    return "\n".join(lines)


def write_snapshot(
    comparisons: list[Comparison],
    exclusions: ExclusionStats,
    path: Path,
    *,
    certs: list[int],
    quarter_ids: list[str],
) -> str:
    """Write the snapshot markdown to `path` and return PASS/FAIL verdict."""
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    if comparisons:
        all_diffs = [c.bp_diff for c in comparisons]
        mean = sum(all_diffs, Decimal(0)) / Decimal(len(all_diffs))
        mx = max(all_diffs)
        gate = "PASS" if mean < DOD_MEAN_BPS and mx < DOD_MAX_BPS else "FAIL"
    else:
        mean = Decimal(0)
        mx = Decimal(0)
        gate = "FAIL (no comparisons)"

    body = "\n".join(
        [
            "# Peerbench — Phase 1 Validation Snapshot",
            "",
            f"**Generated:** {now}",
            f"**Certs:** {', '.join(str(c) for c in sorted(certs))}",
            f"**Quarters:** {', '.join(sorted(quarter_ids))}",
            f"**DoD bar:** mean abs <{DOD_MEAN_BPS} bps, max <{DOD_MAX_BPS} bps",
            "",
            f"**Aggregate:** N={len(comparisons)}, mean={mean:.2f} bps, "
            f"max={mx:.2f} bps — **{gate}**",
            "",
            "## Excluded from comparison",
            "",
            f"- Ratio has no FDIC pre-computed code mapped: {exclusions.no_fdic_code}",
            f"- Our value not 'ok' (partial / suppressed / NULL): {exclusions.not_ok_quality}",
            f"- FDIC fact row missing or NULL: {exclusions.missing_fdic_fact}",
            "",
            "## Per-ratio breakdown",
            "",
            format_table(comparisons),
            "",
        ]
    )
    path.write_text(body)
    return gate
