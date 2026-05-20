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
