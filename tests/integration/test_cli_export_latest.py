"""Verify the `peerbench export --quarter latest` sentinel resolves to MAX(quarter_id)."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from peerbench.db import Quarter, get_session


@pytest.mark.integration
def test_resolve_latest_quarter_id() -> None:
    """Importable helper resolves to the most recent quarter_id in the DB."""
    from peerbench.cli import _resolve_latest_quarter_id

    with get_session() as session:
        latest = _resolve_latest_quarter_id(session)
        quarter_ids = session.scalars(select(Quarter.quarter_id)).all()
        assert latest == max(quarter_ids)
