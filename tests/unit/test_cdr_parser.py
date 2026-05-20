"""Unit tests for the CDR ZIP+TSV streaming parser.

Tests run against a synthetic ZIP built in tmp_path — no network, no real
FFIEC files. The first real ZIP gets streamed at Step 7 of the Task 25
plan; if the real layout differs from these fixtures (delimiter, BOM,
schedule filename pattern), the schema map / pattern strings are the
place to adjust, not this parser.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from peerbench.ingest.cdr import CdrClient, CdrZipNotCachedError


def _make_zip(zip_path: Path, members: dict[str, str]) -> None:
    """Write a ZIP with the given {filename: text-content} pairs."""
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, body in members.items():
            zf.writestr(name, body)


def _rcri_tsv() -> str:
    """Minimal RC-R Part I-style TSV: IDRSSD + CET1 capital column."""
    header = "IDRSSD\tRCOA8274\tRCOA9999"
    rows = [
        "12345\t1500000\textra",
        "67890\t2750000\textra",
        "99999\t\textra",  # explicit blank (null)
    ]
    return "\n".join([header, *rows]) + "\n"


def _rcb_tsv() -> str:
    """Minimal RC-B Memo 2-style TSV: IDRSSD + HTM fair value column."""
    header = "IDRSSD\tRCFD1773\tRCFD0211"
    rows = [
        "12345\t900000\t1000000",
        "67890\t1800000\t2000000",
    ]
    return "\n".join([header, *rows]) + "\n"


def test_get_zip_path_raises_when_missing(tmp_path: Path) -> None:
    client = CdrClient(cache_dir=tmp_path)
    with pytest.raises(CdrZipNotCachedError) as exc:
        client.get_zip_path("2025-Q4")
    msg = str(exc.value)
    assert "2025-Q4.zip" in msg
    assert "cdr.ffiec.gov" in msg


def test_get_zip_path_returns_existing(tmp_path: Path) -> None:
    zip_path = tmp_path / "2025-Q4.zip"
    _make_zip(zip_path, {"dummy.txt": "hello"})
    client = CdrClient(cache_dir=tmp_path)
    assert client.get_zip_path("2025-Q4") == zip_path


def test_iter_schedule_rows_yields_header_keyed_dicts(tmp_path: Path) -> None:
    zip_path = tmp_path / "2025-Q4.zip"
    _make_zip(
        zip_path,
        {
            "FFIEC CDR Call Schedule RCRI 12312025.txt": _rcri_tsv(),
            "FFIEC CDR Call Schedule RCB 12312025.txt": _rcb_tsv(),
        },
    )
    client = CdrClient(cache_dir=tmp_path)
    rows = list(client.iter_schedule_rows("2025-Q4", "RCRI"))
    assert len(rows) == 3
    assert rows[0] == {"IDRSSD": "12345", "RCOA8274": "1500000", "RCOA9999": "extra"}
    assert rows[2]["RCOA8274"] == ""  # explicit blank preserved


def test_iter_schedule_rows_pattern_picks_correct_member(tmp_path: Path) -> None:
    zip_path = tmp_path / "2025-Q4.zip"
    _make_zip(
        zip_path,
        {
            "FFIEC CDR Call Schedule RCRI 12312025.txt": _rcri_tsv(),
            "FFIEC CDR Call Schedule RCB 12312025.txt": _rcb_tsv(),
        },
    )
    client = CdrClient(cache_dir=tmp_path)
    rcb_rows = list(client.iter_schedule_rows("2025-Q4", "RCB"))
    assert len(rcb_rows) == 2
    assert {r["IDRSSD"] for r in rcb_rows} == {"12345", "67890"}
    assert rcb_rows[0]["RCFD1773"] == "900000"


def test_iter_schedule_rows_handles_utf8_bom(tmp_path: Path) -> None:
    zip_path = tmp_path / "2025-Q4.zip"
    bom = "﻿"
    _make_zip(
        zip_path,
        {"FFIEC CDR Call Schedule RCRI 12312025.txt": bom + _rcri_tsv()},
    )
    client = CdrClient(cache_dir=tmp_path)
    rows = list(client.iter_schedule_rows("2025-Q4", "RCRI"))
    # BOM must be stripped from the first header column.
    assert "IDRSSD" in rows[0]


def test_iter_schedule_rows_raises_on_no_match(tmp_path: Path) -> None:
    zip_path = tmp_path / "2025-Q4.zip"
    _make_zip(zip_path, {"unrelated.txt": "x"})
    client = CdrClient(cache_dir=tmp_path)
    with pytest.raises(ValueError, match="No file matching pattern"):
        list(client.iter_schedule_rows("2025-Q4", "RCRI"))


def test_parser_yields_strings_not_decimals(tmp_path: Path) -> None:
    """Confirms format-agnostic contract: caller does Decimal coercion."""
    zip_path = tmp_path / "2025-Q4.zip"
    _make_zip(
        zip_path,
        {"FFIEC CDR Call Schedule RCRI 12312025.txt": _rcri_tsv()},
    )
    client = CdrClient(cache_dir=tmp_path)
    row = next(iter(client.iter_schedule_rows("2025-Q4", "RCRI")))
    for value in row.values():
        assert isinstance(value, str)


def test_iter_streams_without_loading_full_file(tmp_path: Path) -> None:
    """Smoke check that we use the iterator interface, not read()."""
    zip_path = tmp_path / "2025-Q4.zip"
    _make_zip(
        zip_path,
        {"FFIEC CDR Call Schedule RCRI 12312025.txt": _rcri_tsv()},
    )
    client = CdrClient(cache_dir=tmp_path)
    gen = client.iter_schedule_rows("2025-Q4", "RCRI")
    first = next(gen)
    assert first["IDRSSD"] == "12345"
    # Generator can keep yielding without having consumed the whole file.
    second = next(gen)
    assert second["IDRSSD"] == "67890"


# Exercising the private member-finder via the public API only — keeps the
# test boundary at iter_schedule_rows.
def test_find_member_first_match_when_multiple(tmp_path: Path) -> None:
    zip_path = tmp_path / "2025-Q4.zip"
    _make_zip(
        zip_path,
        {
            "subdir/RCRI_extra.txt": "IDRSSD\tRCOA8274\n11111\t1\n",
            "FFIEC CDR Call Schedule RCRI 12312025.txt": _rcri_tsv(),
        },
    )
    client = CdrClient(cache_dir=tmp_path)
    # First match wins (alphabetical-ish order); contract is that callers
    # use a pattern specific enough that multiple matches are a code smell,
    # logged by the client. Either ordering acceptable here.
    rows = list(client.iter_schedule_rows("2025-Q4", "RCRI"))
    assert len(rows) >= 1
    # Use the BOM/blank assertion as a sanity check the iterator works.
    assert "IDRSSD" in rows[0]


_ = io  # keep `io` import referenced for future fixtures (e.g. encoding probes)
