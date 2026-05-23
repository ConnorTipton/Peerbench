from __future__ import annotations

from datetime import UTC, datetime

from peerbench.export.data.cover import build_cover


def test_build_cover_populates_required_fields() -> None:
    cover = build_cover(
        anchor_cert=4063,
        anchor_name="MidFirst Bank",
        quarter_id="2025-Q4",
        quarter_end_date=datetime(2025, 12, 31, tzinfo=UTC).date(),
        generated_at=datetime(2026, 5, 23, 12, 0, 0, tzinfo=UTC),
        data_vintage=datetime(2026, 5, 22, 6, 11, 42, tzinfo=UTC),
    )
    assert cover.anchor_cert == 4063
    assert cover.anchor_name == "MidFirst Bank"
    assert cover.quarter_id == "2025-Q4"
    assert cover.quarter_end == "December 31, 2025"
    assert cover.data_vintage == "2026-05-22"


def test_build_cover_no_extra_notes_by_default() -> None:
    cover = build_cover(
        anchor_cert=4063,
        anchor_name="MidFirst",
        quarter_id="2025-Q4",
        quarter_end_date=datetime(2025, 12, 31, tzinfo=UTC).date(),
        generated_at=datetime(2026, 5, 23, tzinfo=UTC),
        data_vintage=datetime(2026, 5, 22, tzinfo=UTC),
    )
    assert cover.notes == []


def test_build_cover_anchor_warning_note_when_no_ratios() -> None:
    cover = build_cover(
        anchor_cert=4063,
        anchor_name="MidFirst",
        quarter_id="2025-Q4",
        quarter_end_date=datetime(2025, 12, 31, tzinfo=UTC).date(),
        generated_at=datetime(2026, 5, 23, tzinfo=UTC),
        data_vintage=datetime(2026, 5, 22, tzinfo=UTC),
        anchor_has_no_ratios=True,
    )
    assert "Anchor has no ratios for 2025-Q4" in cover.notes[0]


def test_build_cover_no_peers_warning_note() -> None:
    cover = build_cover(
        anchor_cert=4063,
        anchor_name="MidFirst",
        quarter_id="2025-Q4",
        quarter_end_date=datetime(2025, 12, 31, tzinfo=UTC).date(),
        generated_at=datetime(2026, 5, 23, tzinfo=UTC),
        data_vintage=datetime(2026, 5, 22, tzinfo=UTC),
        active_peer_count=0,
    )
    assert any("no active peers" in n.lower() for n in cover.notes)
