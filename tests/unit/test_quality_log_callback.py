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


class TestQualityLogCallback:
    def test_diff_writes_log_row_and_flips_ratios(self) -> None:
        session = _make_session()
        cb = make_quality_log_callback(session)

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

        # One UPDATE issued against Ratio.
        assert session.execute.call_count == 1
        stmt = session.execute.call_args[0][0]
        # Inspect compiled SQL: should be an UPDATE on ratios with a
        # `data_quality='partial'` set clause and a cert+quarter filter.
        compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        assert compiled.startswith("UPDATE ratios")
        assert "data_quality='partial'" in compiled.replace('"', "'")
        assert "ratios.cert = 4063" in compiled
        assert "ratios.quarter_id = '2025-Q4'" in compiled

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
