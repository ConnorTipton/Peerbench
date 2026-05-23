"""Workbook orchestration."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session


def run_export(
    session: Session,
    *,
    anchor_cert: int,
    quarter_id: str,
    out_dir: Path,
) -> Path:
    # Implemented in Task 14 of the Phase 4.2 plan.
    raise NotImplementedError
