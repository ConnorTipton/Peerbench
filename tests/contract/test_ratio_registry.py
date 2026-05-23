"""Load-bearing contract test for the ratio registry.

Enforces invariants the rest of the pipeline assumes:

  1. data/ratios.csv ↔ handler registry are in 1:1 correspondence.
  2. Every CSV row has non-empty numerator/denominator/category formulas.
  3. JSON cells (regulatory_threshold, suppress_when) parse.
  4. Every suppress_when key is from the known set (today: {'cblr'}).
  5. Every handler is at version 'v1' on first publish; a body change
     without a version bump is caught by the AST-hash snapshot.
  6. No `float(...)` cast appears in value-path modules — Decimal end-to-end
     is the only way to hit the <2 bps DoD.
  7. Every ``f.avg(...)`` call uses ``periods=f.quarter_number + 1`` — the
     restatement detector's YTD-forward-quarters helper bakes in that
     pattern, so a divergent ``periods`` expression would silently mis-mark
     downstream quarters.
  8. ``extract_avg_field_deps`` returns the expected ratio→avg-field mapping;
     keeps the cross-quarter recompute trigger surface in lock-step with
     handler bodies.

To intentionally change a handler body: bump @ratio(version=...) AND
regenerate the snapshot (delete it; the test recreates and fails once).
"""

from __future__ import annotations

import ast
import inspect
import json
import re
import textwrap
from pathlib import Path
from typing import Any

import pytest

from peerbench.ratio_defs_io import load_ratio_defs
from peerbench.ratio_engine import registered_handlers
from peerbench.ratio_engine.field_deps import extract_avg_field_deps, extract_field_deps

KNOWN_SUPPRESS_KEYS: frozenset[str] = frozenset({"cblr"})

VALUE_PATH_MODULES: tuple[Path, ...] = (
    Path("src/peerbench/decimal_.py"),
    Path("src/peerbench/ingest/cdr.py"),
    Path("src/peerbench/ingest/fdic.py"),
    Path("src/peerbench/ingest/upsert.py"),
    Path("src/peerbench/ratio_engine/registry.py"),
    Path("src/peerbench/ratio_engine/fact_view.py"),
    Path("src/peerbench/ratio_engine/suppression.py"),
    Path("src/peerbench/ratio_engine/compute.py"),
    Path("src/peerbench/ratio_engine/handlers"),
    Path("src/peerbench/validate.py"),
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = Path(__file__).parent / "handler_ast_snapshot.json"
FIELD_DEPS_SNAPSHOT = REPO_ROOT / "web" / "lib" / "ratio-field-deps.generated.json"


@pytest.fixture(scope="module")
def csv_rows() -> list[Any]:
    return load_ratio_defs()


class TestRegistryCsvParity:
    def test_csv_and_handlers_in_one_to_one_correspondence(self, csv_rows: list[Any]) -> None:
        csv_ids = {r.ratio_id for r in csv_rows}
        handler_ids = set(registered_handlers().keys())
        assert csv_ids == handler_ids, (
            f"in CSV only: {sorted(csv_ids - handler_ids)} | "
            f"in handlers only: {sorted(handler_ids - csv_ids)}"
        )

    def test_csv_rows_have_non_empty_formulas(self, csv_rows: list[Any]) -> None:
        for r in csv_rows:
            assert r.numerator_formula.strip(), f"empty numerator for {r.ratio_id}"
            assert r.denominator_formula.strip(), f"empty denominator for {r.ratio_id}"
            assert r.category.strip(), f"empty category for {r.ratio_id}"
            assert r.display_name.strip(), f"empty display_name for {r.ratio_id}"


class TestSuppressionKeys:
    def test_suppress_when_uses_only_known_keys(self, csv_rows: list[Any]) -> None:
        for r in csv_rows:
            if r.suppress_when is None:
                continue
            unknown = set(r.suppress_when.keys()) - KNOWN_SUPPRESS_KEYS
            assert not unknown, (
                f"ratio {r.ratio_id} has unknown suppress_when keys: {unknown}; "
                f"known: {sorted(KNOWN_SUPPRESS_KEYS)}"
            )


class TestHandlerVersions:
    def test_all_handlers_at_v1(self) -> None:
        non_v1 = {rid: h.version for rid, h in registered_handlers().items() if h.version != "v1"}
        assert not non_v1, f"unexpected versions (Day 2 ships at v1): {non_v1}"


class TestAstHashSnapshot:
    """The snapshot records the AST hash of every handler body. Editing a
    handler without bumping its version trips this test.

    First run: writes the snapshot and skips (you must commit it).
    Subsequent runs: compares; mismatches fail the test.
    """

    def test_handler_ast_hashes_match_snapshot(self) -> None:
        current = {
            rid: {"version": h.version, "ast_hash": h.ast_hash}
            for rid, h in sorted(registered_handlers().items())
        }
        if not SNAPSHOT.exists():
            SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
            SNAPSHOT.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
            pytest.skip(f"wrote initial snapshot to {SNAPSHOT}; commit it and re-run")
        snapshot = json.loads(SNAPSHOT.read_text())
        diffs: list[str] = []
        for rid, entry in current.items():
            snap_entry = snapshot.get(rid)
            if snap_entry is None:
                diffs.append(f"  {rid}: not in snapshot (new handler)")
                continue
            if entry["version"] != snap_entry["version"]:
                diffs.append(f"  {rid}: version {snap_entry['version']!r} → {entry['version']!r}")
            if entry["ast_hash"] != snap_entry["ast_hash"]:
                diffs.append(
                    f"  {rid}: ast_hash drifted "
                    f"({snap_entry['ast_hash']} → {entry['ast_hash']}); "
                    "did you forget to bump @ratio(version=...) ?"
                )
        for rid in snapshot:
            if rid not in current:
                diffs.append(f"  {rid}: in snapshot but not in registry (deleted handler)")
        assert not diffs, (
            "Handler registry has drifted from the snapshot. Either bump\n"
            "@ratio(version=...) for any intentionally-changed handler, or\n"
            "regenerate the snapshot by deleting "
            f"{SNAPSHOT} and re-running.\n\n" + "\n".join(diffs)
        )


class TestFieldDepsSnapshot:
    """The committed JSON at ``web/lib/ratio-field-deps.generated.json`` is the
    contract between the Python handler bodies (single source of truth for
    field dependencies) and the dashboard's per-cell restatement marker. Both
    the web layer and the ingest restatement-detector callback read from it,
    so drift between handler edits and this snapshot would silently break the
    "mark only the affected ratio" guarantee in Phase 2's definition of done.

    Regenerate with ``uv run peerbench export-field-deps`` after intentional
    handler edits, then commit the JSON.
    """

    def test_field_deps_snapshot_matches_handler_bodies(self) -> None:
        current = {rid: sorted(fields) for rid, fields in extract_field_deps().items()}
        assert FIELD_DEPS_SNAPSHOT.exists(), (
            f"missing field-deps snapshot at {FIELD_DEPS_SNAPSHOT.relative_to(REPO_ROOT)}; "
            "regenerate with `uv run peerbench export-field-deps`"
        )
        snapshot = json.loads(FIELD_DEPS_SNAPSHOT.read_text())
        diffs: list[str] = []
        for rid in sorted(set(current) | set(snapshot)):
            cur = current.get(rid)
            snap = snapshot.get(rid)
            if cur is None:
                diffs.append(f"  {rid}: in snapshot but no handler registered")
            elif snap is None:
                diffs.append(f"  {rid}: handler exists but missing from snapshot (fields: {cur})")
            elif cur != snap:
                diffs.append(f"  {rid}: snapshot {snap} -> handler now reads {cur}")
        assert not diffs, (
            "field-deps snapshot has drifted from handler bodies. Regenerate\n"
            "with `uv run peerbench export-field-deps` and commit the result:\n\n"
            + "\n".join(diffs)
        )

    def test_suppression_deps_are_unioned_into_consumer_ratios(self) -> None:
        """``suppress_when={"cblr": true}`` reads CBLRIND via ``should_suppress``,
        not from the handler body. The dep graph must still surface that edge,
        otherwise a CBLRIND restatement would skip the partial flip on the very
        ratios whose data_quality flips between ``ok`` and ``suppressed``.

        Codex review caught this gap on the Sprint 1 polish diff (P1).
        """
        deps = extract_field_deps()
        for rid in ("cet1", "tier1_rbc", "total_rbc"):
            assert "CBLRIND" in deps[rid], (
                f"{rid} opts into CBLR suppression but its field deps are missing "
                f"CBLRIND. Got: {sorted(deps[rid])}"
            )
        # And ratios that don't opt into CBLR suppression should NOT pick up CBLRIND.
        for rid in ("nim", "roa", "acl_loans"):
            assert "CBLRIND" not in deps[rid], (
                f"{rid} does not opt into CBLR suppression but picked up CBLRIND: "
                f"{sorted(deps[rid])}"
            )


class TestAvgPattern:
    """Every ``f.avg(...)`` call must use ``periods=f.quarter_number + 1``.

    The restatement detector's :func:`_ytd_forward_quarters` helper assumes
    YTD-style averaging: forward window is the rest of the same FDIC year,
    or all four next-year quarters when the restatement lands on Q4. A
    handler that uses a constant or a different expression — say
    ``periods=4`` or ``periods=f.quarter_number * 2`` — would have a
    different look-back window and the forward flip would silently be
    wrong (over- or under-marking).

    If you have a legitimate reason to use a different averaging window,
    extend ``_ytd_forward_quarters`` to dispatch on the per-handler pattern
    AND extend this test to allow-list the new pattern. Don't just bypass.
    """

    def _iter_avg_calls(self) -> list[tuple[str, ast.Call]]:
        from peerbench.ratio_engine.handlers import (
            asset_quality,
            balance_sheet,
            capital,
            concentration,
            liquidity,
            profitability,
            yields,
        )

        modules = (
            asset_quality,
            balance_sheet,
            capital,
            concentration,
            liquidity,
            profitability,
            yields,
        )
        calls: list[tuple[str, ast.Call]] = []
        for mod in modules:
            source = textwrap.dedent(inspect.getsource(mod))
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "avg"
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "f"
                ):
                    calls.append((mod.__name__, node))
        return calls

    def test_every_f_avg_uses_quarter_number_plus_one(self) -> None:
        offenders: list[str] = []
        for mod_name, call in self._iter_avg_calls():
            periods_kw = next((kw for kw in call.keywords if kw.arg == "periods"), None)
            if periods_kw is None:
                offenders.append(f"{mod_name}: f.avg(...) without periods= kwarg")
                continue
            expr = periods_kw.value
            # Expected: BinOp( Attribute(value=Name('f'), attr='quarter_number'), Add(), Constant(1) )
            ok = (
                isinstance(expr, ast.BinOp)
                and isinstance(expr.op, ast.Add)
                and isinstance(expr.left, ast.Attribute)
                and expr.left.attr == "quarter_number"
                and isinstance(expr.left.value, ast.Name)
                and expr.left.value.id == "f"
                and isinstance(expr.right, ast.Constant)
                and expr.right.value == 1
            )
            if not ok:
                rendered = ast.unparse(expr)
                offenders.append(
                    f"{mod_name}: f.avg(..., periods={rendered}) — expected f.quarter_number + 1"
                )
        assert not offenders, (
            "f.avg(...) periods expression must be `f.quarter_number + 1` "
            "(the only pattern the YTD-forward-quarters helper in the "
            "restatement detector supports). To use a different look-back, "
            "extend _ytd_forward_quarters AND this test together.\n" + "\n".join(offenders)
        )


class TestAvgFieldDepsSnapshot:
    """Pin the avg-consumer surface so handler edits that change it are
    visible at PR review.

    The set is intentionally small: each new (ratio, field) pair here means
    a new forward-quarter flip the restatement detector will issue on every
    matching diff. Surprises here ripple into per-quarter recompute load
    and into the ``data_quality='partial'`` window the dashboard surfaces.
    """

    def test_avg_field_deps_matches_expected(self) -> None:
        deps = extract_avg_field_deps()
        # Ratios that have any avg-consumer fields. Everything else must
        # have an empty frozenset (no f.avg reads, directly or transitively).
        non_empty = {rid: sorted(fields) for rid, fields in deps.items() if fields}
        expected = {
            "nco_ratio": ["LNLSGR"],
            "cost_funds": ["DEPI"],
            # nis → cost_funds via RATIO_DEPENDENCIES; transitive closure
            # surfaces DEPI on nis so a DEPI restatement also marks the
            # forward nis rows stale.
            "nis": ["DEPI"],
        }
        assert non_empty == expected, (
            f"avg-consumer surface drifted; got {non_empty}, expected {expected}. "
            "If this is intentional, update the expected map AND audit the "
            "restatement detector's forward-flip behavior for the new edges."
        )


FLOAT_CAST = re.compile(r"\bfloat\(")
# rate_limit.py uses floats for timing — that's not a value path.
FLOAT_CAST_ALLOWED: frozenset[Path] = frozenset({Path("src/peerbench/ingest/rate_limit.py")})


class TestNoFloatInValuePath:
    """Reject any `float(` cast in the modules that touch values. Single-
    line bug-reproduction policy: if you really need float (e.g. for a
    rate-limit timing helper) put it in a non-value-path module."""

    def _iter_py_files(self) -> list[Path]:
        files: list[Path] = []
        for target in VALUE_PATH_MODULES:
            full = REPO_ROOT / target
            if full.is_file():
                files.append(full)
            elif full.is_dir():
                files.extend(p for p in full.rglob("*.py") if "__pycache__" not in p.parts)
        return files

    def test_no_float_cast_in_value_path(self) -> None:
        offenders: list[str] = []
        for path in self._iter_py_files():
            rel = path.relative_to(REPO_ROOT)
            if rel in FLOAT_CAST_ALLOWED:
                continue
            for line_num, line in enumerate(path.read_text().splitlines(), start=1):
                stripped = line.lstrip()
                if stripped.startswith("#"):
                    continue
                if FLOAT_CAST.search(line):
                    offenders.append(f"{rel}:{line_num}: {line.strip()}")
        assert not offenders, (
            "found `float(...)` cast in value path — Decimal end-to-end "
            "discipline is non-negotiable for the <2 bps DoD:\n" + "\n".join(offenders)
        )
