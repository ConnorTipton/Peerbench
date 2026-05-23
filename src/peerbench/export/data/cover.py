"""Build the Cover tab payload."""

from __future__ import annotations

from datetime import date, datetime

from peerbench.export.data.types import CoverTab


def build_cover(
    *,
    anchor_cert: int,
    anchor_name: str,
    quarter_id: str,
    quarter_end_date: date,
    generated_at: datetime,
    data_vintage: datetime,
    anchor_has_no_ratios: bool = False,
    active_peer_count: int | None = None,
) -> CoverTab:
    notes: list[str] = []
    if anchor_has_no_ratios:
        notes.append(f"Anchor has no ratios for {quarter_id}.")
    if active_peer_count == 0:
        notes.append(
            "No active peers in the institutions table — workbook contains anchor data only."
        )
    return CoverTab(
        anchor_cert=anchor_cert,
        anchor_name=anchor_name,
        quarter_id=quarter_id,
        quarter_end=f"{quarter_end_date.strftime('%B')} {quarter_end_date.day}, {quarter_end_date.year}",
        generated_at=generated_at,
        data_vintage=data_vintage.strftime("%Y-%m-%d"),
        notes=notes,
    )
