"""Verify `peerbench export --quarter latest` resolves to MAX(ratios.quarter_id).

Anchoring on the ratios table (not the quarters table) matches the dashboard's
`getMatrixData` resolution and avoids publishing an empty-quarter workbook
when a Quarter row exists ahead of any computed ratios.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from peerbench.db import Ratio, get_session


@pytest.mark.integration
def test_resolve_latest_quarter_id() -> None:
    """Importable helper resolves to the most recent quarter with ratios."""
    from peerbench.cli import _resolve_latest_quarter_id

    with get_session() as session:
        latest = _resolve_latest_quarter_id(session)
        ratio_quarter_ids = session.scalars(select(Ratio.quarter_id).distinct()).all()
        assert latest == max(ratio_quarter_ids)
