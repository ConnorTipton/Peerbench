"""Verify the `peerbench export --quarter latest` sentinel resolves to MAX(quarter_id)."""

from __future__ import annotations

from peerbench.db import Quarter, get_session


def test_resolve_latest_quarter_id() -> None:
    """Importable helper resolves to the most recent quarter_id in the DB."""
    from peerbench.cli import _resolve_latest_quarter_id

    with get_session() as session:
        latest = _resolve_latest_quarter_id(session)
        max_in_db = max(q.quarter_id for q in session.query(Quarter).all())
        assert latest == max_in_db
