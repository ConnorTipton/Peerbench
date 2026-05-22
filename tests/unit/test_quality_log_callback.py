"""Unit tests for the restatement-detector callback.

DB-touching round trip is covered by the manual smoke test in the Day 4
verification checklist. These tests assert the callback's session
side-effects via a mock — adequate for the simple add/execute pair the
callback issues.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock

from sqlalchemy.orm import Session

from peerbench.db.models import QualityLog, Ratio
from peerbench.ingest.quality_log import make_quality_log_callback


def _make_session() -> MagicMock:
    """Return a MagicMock posing as a SQLAlchemy Session."""
    session = MagicMock(spec=Session)
    return session


def _compiled_update(session: MagicMock) -> str:
    stmt = session.execute.call_args[0][0]
    return str(stmt.compile(compile_kwargs={"literal_binds": True})).replace('"', "'")


class TestQualityLogCallback:
    def test_diff_writes_log_row_and_scopes_partial_flip_to_consumers(self) -> None:
        session = _make_session()
        cb = make_quality_log_callback(session)

        # NIM is consumed by handlers: nim, eff_ratio, ppnr_assets,
        # nonint_inc_rev. The partial flip should target exactly those.
        cb(4063, "2025-Q4", "NIM", Decimal("100.00"), Decimal("110.00"))

        # One QualityLog inserted.
        assert session.add.call_count == 1
        added = session.add.call_args[0][0]
        assert isinstance(added, QualityLog)
        assert added.cert == 4063
        assert added.quarter_id == "2025-Q4"
        assert added.field_code == "NIM"
        assert added.event_type == "restated"
        assert added.old_value == Decimal("100.00")
        assert added.new_value == Decimal("110.00")

        # One UPDATE issued, scoped to (cert, quarter, ratio_id IN ...).
        assert session.execute.call_count == 1
        compiled = _compiled_update(session)
        assert compiled.startswith("UPDATE ratios")
        assert "data_quality='partial'" in compiled
        assert "ratios.cert = 4063" in compiled
        assert "ratios.quarter_id = '2025-Q4'" in compiled
        # IN-list scoping — Codex P2 regression guard from the Sprint 1 review.
        for consumer in ("nim", "eff_ratio", "ppnr_assets", "nonint_inc_rev"):
            assert f"'{consumer}'" in compiled, (
                f"{consumer} reads NIM but is missing from the partial-flip IN-list: {compiled}"
            )
        # And no unrelated ratio sneaks in.
        for unrelated in ("cet1", "tier1_lev", "acl_loans", "loans_deposits"):
            assert f"'{unrelated}'" not in compiled, (
                f"{unrelated} does not read NIM but appears in IN-list: {compiled}"
            )

    def test_restatement_of_unconsumed_field_logs_but_skips_partial_flip(self) -> None:
        # An FFIEC code with no handler consumer (e.g. a field we ingest for
        # future use) should still produce a quality_log row but trigger zero
        # ratio updates — there's nothing affected to mark partial.
        session = _make_session()
        cb = make_quality_log_callback(session)

        cb(4063, "2025-Q4", "__NEVER_READ_BY_ANY_HANDLER__", Decimal("1"), Decimal("2"))

        assert session.add.call_count == 1
        assert session.execute.call_count == 0

    def test_cblrind_restatement_flips_cblr_suppressed_ratios(self) -> None:
        # CBLRIND is read by `should_suppress`, not by any handler body. The
        # field-deps walker unions in suppression edges so a CBLRIND
        # restatement flips cet1/tier1_rbc/total_rbc — the very ratios whose
        # data_quality moves between 'ok' and 'suppressed' based on the flag.
        # Without the suppression-dep union, this case slipped through and a
        # bank's CBLR election change would silently leave stale `'ok'` rows
        # in the ratios table. (Codex review P1 from the Sprint 1 polish diff.)
        session = _make_session()
        cb = make_quality_log_callback(session)

        cb(4063, "2025-Q4", "CBLRIND", Decimal("0"), Decimal("1"))

        assert session.execute.call_count == 1
        compiled = _compiled_update(session)
        for rid in ("cet1", "tier1_rbc", "total_rbc"):
            assert f"'{rid}'" in compiled, (
                f"{rid} suppresses on CBLRIND but is missing from the partial-flip "
                f"IN-list: {compiled}"
            )

    def test_value_to_null_transition_is_logged(self) -> None:
        # value -> NULL is a legitimate restatement per upsert.py's design.
        session = _make_session()
        cb = make_quality_log_callback(session)

        cb(4063, "2025-Q4", "NIM", Decimal("100.00"), None)

        assert session.add.call_count == 1
        added = session.add.call_args[0][0]
        assert added.old_value == Decimal("100.00")
        assert added.new_value is None
        assert session.execute.call_count == 1

    def test_null_to_value_transition_is_logged(self) -> None:
        # NULL -> value is also a legitimate restatement.
        session = _make_session()
        cb = make_quality_log_callback(session)

        cb(4063, "2025-Q4", "NIM", None, Decimal("110.00"))

        assert session.add.call_count == 1
        added = session.add.call_args[0][0]
        assert added.old_value is None
        assert added.new_value == Decimal("110.00")
        assert session.execute.call_count == 1

    def test_none_to_none_is_noop(self) -> None:
        # Defensive guard: a caller invoking on_diff directly with no real
        # diff should not produce a log row.
        session = _make_session()
        cb = make_quality_log_callback(session)

        cb(4063, "2025-Q4", "NIM", None, None)

        assert session.add.call_count == 0
        assert session.execute.call_count == 0

    def test_ratio_imported(self) -> None:
        # Sanity import guard so the test file flags accidentally
        # removing the Ratio model reference.
        assert Ratio.__tablename__ == "ratios"


class TestQualityLogCallbackCrossQuarter:
    """Forward-quarter flip for ``f.avg(...)`` consumers (codex P2 from PR #1).

    Two handlers do YTD averaging: ``nco_ratio`` (LNLSGR) and ``cost_funds``
    (DEPI). Each reads ``periods=quarter_number+1`` periods, so a restatement
    at (Y, Q) makes downstream quarters that average back through (Y, Q) stale
    too — the same-quarter flip alone leaves those rows with ``data_quality
    = 'ok'`` until the next compute pass overwrites them, which is wrong:
    between detection and recompute the dashboard renders a stale ``ok``
    value with no indicator.

    Forward-affected quarters under the YTD pattern:

      * (Y, Q1..Q3) restatement → (Y, Q+1..Q4) — rest of the same FDIC year.
      * (Y, Q4) restatement → (Y+1, Q1..Q4) — Q4 is the "prior year-end"
        balance every Y+1 quarter averages in.

    Non-``f.avg`` fields (NIM, NCLNLS, etc.) keep the original same-quarter
    semantics — no forward flip.
    """

    def _compiled_updates(self, session: MagicMock) -> list[str]:
        return [
            str(call.args[0].compile(compile_kwargs={"literal_binds": True})).replace('"', "'")
            for call in session.execute.call_args_list
        ]

    def test_lnlsgr_restatement_in_q2_flips_q3_and_q4_nco_ratio(self) -> None:
        # LNLSGR at 2025-Q2 — nco_ratio uses f.avg("LNLSGR", periods=qnum+1):
        #   2025-Q3 (periods=4) averages Q3, Q2, Q1, prev-Q4 — includes Q2 ✓
        #   2025-Q4 (periods=5) averages Q4, Q3, Q2, Q1, prev-Q4 — includes Q2 ✓
        #   2026-Q1 (periods=2) averages Q1 + prev-Q4(=2025-Q4) — Q2 not included ✗
        session = _make_session()
        cb = make_quality_log_callback(session)

        cb(4063, "2025-Q2", "LNLSGR", Decimal("1000"), Decimal("1010"))

        compiled = self._compiled_updates(session)
        # Two UPDATEs: one for current quarter (nco_ratio + acl_loans +
        # acl_npl + npl_ratio all read LNLSGR), one for forward quarters
        # (nco_ratio is the only f.avg consumer of LNLSGR).
        assert len(compiled) == 2, f"expected current + forward UPDATEs, got {len(compiled)}"
        current_sql, forward_sql = compiled
        assert "ratios.quarter_id = '2025-Q2'" in current_sql
        assert "'nco_ratio'" in forward_sql
        assert "ratios.cert = 4063" in forward_sql
        assert "data_quality='partial'" in forward_sql
        # Forward set: 2025-Q3 + 2025-Q4 — not 2026-Q1 (out of window) or
        # 2025-Q1/Q2 (current-or-prior, not forward).
        for forward_qid in ("2025-Q3", "2025-Q4"):
            assert f"'{forward_qid}'" in forward_sql, (
                f"{forward_qid} should be in the forward IN-list: {forward_sql}"
            )
        for not_forward in ("2026-Q1", "2025-Q1", "2025-Q2"):
            assert f"'{not_forward}'" not in forward_sql, (
                f"{not_forward} is not in the YTD-forward window: {forward_sql}"
            )
        # Non-avg consumers of LNLSGR (acl_loans, npl_ratio, loans_assets)
        # must NOT appear in the forward IN-list — they don't average
        # across quarters, so a Q2 LNLSGR restatement is not load-bearing
        # on Q3 for those ratios.
        for direct_only in ("acl_loans", "npl_ratio", "loans_assets"):
            assert f"'{direct_only}'" not in forward_sql, (
                f"{direct_only} reads LNLSGR directly (not via f.avg) — "
                f"must NOT be in the forward IN-list: {forward_sql}"
            )

    def test_lnlsgr_restatement_in_q4_flips_next_year_q1_through_q4(self) -> None:
        # Year-end balance: every Y+1 quarter averages back to prev-Q4.
        # 2024-Q4 LNLSGR → 2025-Q1..Q4 nco_ratio all stale. 2026-Q1 reads
        # prev-Q4(=2025-Q4), not 2024-Q4 — out of window.
        session = _make_session()
        cb = make_quality_log_callback(session)

        cb(4063, "2024-Q4", "LNLSGR", Decimal("1000"), Decimal("1010"))

        compiled = self._compiled_updates(session)
        assert len(compiled) == 2
        forward_sql = compiled[1]
        for forward_qid in ("2025-Q1", "2025-Q2", "2025-Q3", "2025-Q4"):
            assert f"'{forward_qid}'" in forward_sql, (
                f"{forward_qid} should be in the next-year forward IN-list: {forward_sql}"
            )
        for not_forward in ("2024-Q1", "2024-Q2", "2024-Q3", "2024-Q4", "2026-Q1"):
            assert f"'{not_forward}'" not in forward_sql, (
                f"{not_forward} must not be in next-year forward IN-list: {forward_sql}"
            )

    def test_depi_restatement_flips_forward_cost_funds_and_nis(self) -> None:
        # DEPI is averaged by cost_funds; nis depends on cost_funds via
        # RATIO_DEPENDENCIES. So the forward flip must include BOTH —
        # otherwise nis at Qn+1 renders stale `ok` after the cost_funds
        # value underneath it has been invalidated.
        session = _make_session()
        cb = make_quality_log_callback(session)

        cb(4063, "2025-Q1", "DEPI", Decimal("500"), Decimal("520"))

        compiled = self._compiled_updates(session)
        assert len(compiled) == 2
        forward_sql = compiled[1]
        for rid in ("cost_funds", "nis"):
            assert f"'{rid}'" in forward_sql, (
                f"{rid} averages or transitively-averages DEPI — must be in "
                f"the forward IN-list: {forward_sql}"
            )
        # yield_ea reads INTINC/ERNAST5 directly with no f.avg — must not
        # appear in the forward flip even though nis depends on yield_ea.
        assert "'yield_ea'" not in forward_sql, (
            f"yield_ea does not average DEPI — must not be flipped: {forward_sql}"
        )
        for forward_qid in ("2025-Q2", "2025-Q3", "2025-Q4"):
            assert f"'{forward_qid}'" in forward_sql

    def test_non_avg_field_restatement_does_not_emit_forward_update(self) -> None:
        # NIM is read directly by nim/eff_ratio/ppnr_assets/nonint_inc_rev —
        # no f.avg. A NIM restatement at Q2 must not produce a forward
        # UPDATE — that would over-mark ratios whose Q3 value is genuinely
        # current.
        session = _make_session()
        cb = make_quality_log_callback(session)

        cb(4063, "2025-Q2", "NIM", Decimal("3.50"), Decimal("3.60"))

        # Exactly one UPDATE — the existing same-quarter flip.
        assert session.execute.call_count == 1, (
            f"expected only the same-quarter flip; got "
            f"{session.execute.call_count} UPDATE(s)"
        )

    def test_unconsumed_field_emits_no_forward_update(self) -> None:
        # A field with no avg consumer (and no direct consumer) emits no
        # forward UPDATE — same defensive shape as the unconsumed-field
        # case in the same-quarter tests.
        session = _make_session()
        cb = make_quality_log_callback(session)

        cb(4063, "2025-Q2", "__NEVER_READ__", Decimal("1"), Decimal("2"))

        assert session.execute.call_count == 0
