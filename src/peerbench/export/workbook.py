"""Workbook orchestration. Filled in by Task 14."""

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
    raise NotImplementedError("filled in by Task 14")
