"""Unit tests for peerbench.storage.manifest — pure-function payload builder."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from peerbench.storage.manifest import build_manifest


@pytest.fixture
def workbook_file(tmp_path: Path) -> Path:
    p = tmp_path / "peerbench_4063_2025-Q4.xlsx"
    p.write_bytes(b"x" * 1234)
    return p


def test_manifest_shape_from_real_file(workbook_file: Path) -> None:
    m = build_manifest(
        workbook_file,
        anchor_cert=4063,
        quarter_id="2025-Q4",
        public_url_base="https://abc.supabase.co/storage/v1/object/public/peerbench-exports",
    )
    assert set(m.keys()) == {"url", "generated_at", "quarter_id", "anchor_cert", "size_bytes"}
    assert (
        m["url"] == "https://abc.supabase.co/storage/v1/object/public/peerbench-exports/latest.xlsx"
    )
    assert m["quarter_id"] == "2025-Q4"
    assert m["anchor_cert"] == 4063


def test_manifest_size_matches_stat(workbook_file: Path) -> None:
    m = build_manifest(
        workbook_file,
        anchor_cert=4063,
        quarter_id="2025-Q4",
        public_url_base="https://x/peerbench-exports",
    )
    assert m["size_bytes"] == 1234


def test_manifest_generated_at_is_iso_utc(workbook_file: Path) -> None:
    m = build_manifest(
        workbook_file,
        anchor_cert=4063,
        quarter_id="2025-Q4",
        public_url_base="https://x/peerbench-exports",
    )
    parsed = datetime.fromisoformat(m["generated_at"])
    assert parsed.tzinfo is not None  # must be timezone-aware
    assert m["generated_at"].endswith("+00:00") or m["generated_at"].endswith("Z")


def test_manifest_strips_trailing_slash_on_url_base(workbook_file: Path) -> None:
    m = build_manifest(
        workbook_file,
        anchor_cert=4063,
        quarter_id="2025-Q4",
        public_url_base="https://abc.supabase.co/storage/v1/object/public/peerbench-exports/",
    )
    assert (
        m["url"] == "https://abc.supabase.co/storage/v1/object/public/peerbench-exports/latest.xlsx"
    )


def test_manifest_passes_through_anchor_and_quarter(workbook_file: Path) -> None:
    m = build_manifest(
        workbook_file,
        anchor_cert=5510,
        quarter_id="2024-Q1",
        public_url_base="https://x/peerbench-exports",
    )
    assert m["anchor_cert"] == 5510
    assert m["quarter_id"] == "2024-Q1"
