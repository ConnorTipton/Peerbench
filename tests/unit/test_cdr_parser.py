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
def test_find_member_word_boundary_excludes_attached_token(tmp_path: Path) -> None:
    """The schedule pattern matches as a whole token. `RCRI_extra` shares
    the prefix but is a different identifier, so it must not match."""
    zip_path = tmp_path / "2025-Q4.zip"
    _make_zip(
        zip_path,
        {
            "subdir/RCRI_extra.txt": "IDRSSD\tRCOA8274\n11111\t1\n",
            "FFIEC CDR Call Schedule RCRI 12312025.txt": _rcri_tsv(),
        },
    )
    client = CdrClient(cache_dir=tmp_path)
    rows = list(client.iter_schedule_rows("2025-Q4", "RCRI"))
    assert len(rows) == 3
    # Sanity-check we picked the FFIEC file, not RCRI_extra (single row).
    assert {r["IDRSSD"] for r in rows} == {"12345", "67890", "99999"}


def test_pattern_does_not_match_longer_token(tmp_path: Path) -> None:
    """Real FFIEC ZIPs ship both RCRI (Part I) and RCRII (Part II). A
    substring match would collide; word-boundary matching keeps them
    distinct so the right schedule streams."""
    zip_path = tmp_path / "2025-Q4.zip"
    rcrii_tsv = "IDRSSD\tRCOA9998\n55555\t1\n"
    _make_zip(
        zip_path,
        {
            # RCRII listed first so an alphabetical-order substring match
            # would silently stream Part II under the RCRI pattern.
            "FFIEC CDR Call Schedule RCRII 12312025.txt": rcrii_tsv,
            "FFIEC CDR Call Schedule RCRI 12312025.txt": _rcri_tsv(),
        },
    )
    client = CdrClient(cache_dir=tmp_path)
    rcri_rows = list(client.iter_schedule_rows("2025-Q4", "RCRI"))
    assert all("RCOA8274" in r for r in rcri_rows)
    rcrii_rows = list(client.iter_schedule_rows("2025-Q4", "RCRII"))
    assert all("RCOA9998" in r for r in rcrii_rows)


def test_iter_schedule_rows_raises_when_required_column_missing(tmp_path: Path) -> None:
    """If the live ZIP uses a different domain prefix (RCON vs RCOA), the
    expected MDRM column will be absent and silently producing zero matches
    is the prior bug. The header check must fail loudly."""
    zip_path = tmp_path / "2025-Q4.zip"
    bad_tsv = "IDRSSD\tRCOA9999\n12345\t1\n"
    _make_zip(zip_path, {"FFIEC CDR Call Schedule RCRI 12312025.txt": bad_tsv})
    client = CdrClient(cache_dir=tmp_path)
    with pytest.raises(ValueError, match="missing required column"):
        list(
            client.iter_schedule_rows(
                "2025-Q4", "RCRI", required_columns=(("RCOA8274",),)
            )
        )


def test_iter_schedule_rows_fans_in_across_split_files(tmp_path: Path) -> None:
    """RCB ships split as `(1 of 2).txt` + `(2 of 2).txt` in real FFIEC
    ZIPs (confirmed in cache/cdr/2025-Q4.zip). Banks are row-split: First-
    Citizens is in part 1; some of the 5-bank sample lands in part 2. The
    parser must iterate ALL matching members so no bank is silently dropped.
    """
    zip_path = tmp_path / "2025-Q4.zip"
    rcb_part1 = "IDRSSD\tRCFD1773\n11111\t100\n22222\t200\n"
    rcb_part2 = "IDRSSD\tRCFD1773\n33333\t300\n44444\t400\n"
    _make_zip(
        zip_path,
        {
            "FFIEC CDR Call Schedule RCB 12312025(1 of 2).txt": rcb_part1,
            "FFIEC CDR Call Schedule RCB 12312025(2 of 2).txt": rcb_part2,
        },
    )
    client = CdrClient(cache_dir=tmp_path)
    rows = list(client.iter_schedule_rows("2025-Q4", "RCB"))
    rssds = {r["IDRSSD"] for r in rows}
    assert rssds == {"11111", "22222", "33333", "44444"}


def test_required_columns_group_satisfied_by_any_candidate(tmp_path: Path) -> None:
    """For multi-domain MDRMs (RCOAP859 vs RCFAP859), the header check is
    'at least one of these candidates is present', not 'all present'."""
    zip_path = tmp_path / "2025-Q4.zip"
    # Domestic-only filer fixture: RCOAP859 present, RCFAP859 absent.
    tsv = "IDRSSD\tRCOAP859\n12345\t1500000\n"
    _make_zip(zip_path, {"FFIEC CDR Call Schedule RCRI 12312025.txt": tsv})
    client = CdrClient(cache_dir=tmp_path)
    rows = list(
        client.iter_schedule_rows(
            "2025-Q4",
            "RCRI",
            required_columns=(("IDRSSD",), ("RCOAP859", "RCFAP859")),
        )
    )
    assert len(rows) == 1
    assert rows[0]["RCOAP859"] == "1500000"


def test_required_columns_group_fails_when_none_present(tmp_path: Path) -> None:
    """If the header has zero candidates from a required group, fail loud
    (layout drift / wrong MDRM family). This preserves the post-Task-25
    'no silent zero matches' contract."""
    zip_path = tmp_path / "2025-Q4.zip"
    bad_tsv = "IDRSSD\tRCOA9999\n12345\t1\n"
    _make_zip(zip_path, {"FFIEC CDR Call Schedule RCRI 12312025.txt": bad_tsv})
    client = CdrClient(cache_dir=tmp_path)
    with pytest.raises(ValueError, match="missing required column"):
        list(
            client.iter_schedule_rows(
                "2025-Q4",
                "RCRI",
                required_columns=(("RCOAP859", "RCFAP859"),),
            )
        )


def test_pick_first_non_empty_walks_candidates() -> None:
    """Helper that consumers (cli.py:ingest_cdr) use to resolve a single
    value across the candidate column tuple from cdr_columns()."""
    from peerbench.ingest.cdr import pick_first_non_empty

    row = {"IDRSSD": "12345", "RCOAP859": "", "RCFAP859": "1500000"}
    assert pick_first_non_empty(row, ("RCOAP859", "RCFAP859")) == "1500000"

    row2 = {"IDRSSD": "12345", "RCOAP859": "  ", "RCFAP859": ""}
    assert pick_first_non_empty(row2, ("RCOAP859", "RCFAP859")) is None

    row3 = {"IDRSSD": "12345", "RCOAP859": "9", "RCFAP859": "1"}
    # First non-empty wins; doesn't blend or sum.
    assert pick_first_non_empty(row3, ("RCOAP859", "RCFAP859")) == "9"


def test_iter_schedule_rows_required_columns_default_off(tmp_path: Path) -> None:
    """Empty `required_columns` keeps the old permissive behavior for
    callers that don't care to validate (today: tests + future probes)."""
    zip_path = tmp_path / "2025-Q4.zip"
    _make_zip(zip_path, {"FFIEC CDR Call Schedule RCRI 12312025.txt": _rcri_tsv()})
    client = CdrClient(cache_dir=tmp_path)
    rows = list(client.iter_schedule_rows("2025-Q4", "RCRI"))
    assert len(rows) == 3


_ = io  # keep `io` import referenced for future fixtures (e.g. encoding probes)
