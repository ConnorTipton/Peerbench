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
        list(client.iter_schedule_rows("2025-Q4", "RCRI", required_columns=(("RCOA8274",),)))


def test_iter_schedule_rows_fans_in_across_split_files(tmp_path: Path) -> None:
    """Row-split shape: both parts share the target column. The parser must
    iterate ALL matching members so no bank is silently dropped."""
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


def test_iter_schedule_rows_skips_members_lacking_required_columns(tmp_path: Path) -> None:
    """Column-split shape (real RC-B 2025-Q4 layout): part 1 has the
    target MDRM, part 2 carries a disjoint set of memorandum-item MDRMs.
    With `required_columns=((target,),)` the parser must SKIP part 2
    rather than fail — but still raise loudly if NO member has the
    target across all candidates."""
    zip_path = tmp_path / "2025-Q4.zip"
    # Part 1: target column present (4 banks).
    rcb_part1 = "IDRSSD\tRCFD1773\n11111\t100\n22222\t200\n"
    # Part 2: same banks but different MDRMs (no RCFD1773).
    rcb_part2 = "IDRSSD\tRCONG349\n11111\t9\n22222\t8\n"
    _make_zip(
        zip_path,
        {
            "FFIEC CDR Call Schedule RCB 12312025(1 of 2).txt": rcb_part1,
            "FFIEC CDR Call Schedule RCB 12312025(2 of 2).txt": rcb_part2,
        },
    )
    client = CdrClient(cache_dir=tmp_path)
    rows = list(
        client.iter_schedule_rows(
            "2025-Q4",
            "RCB",
            required_columns=(("IDRSSD",), ("RCFD1773",)),
        )
    )
    assert len(rows) == 2
    assert {r["IDRSSD"] for r in rows} == {"11111", "22222"}
    assert all(r["RCFD1773"] in {"100", "200"} for r in rows)


def test_iter_schedule_rows_raises_when_no_member_has_required(tmp_path: Path) -> None:
    """Multi-file ZIP where NO matching member has the required MDRM —
    e.g. live ZIP uses a brand-new domain prefix family across both parts.
    Must fail loudly so the schema map gets updated."""
    zip_path = tmp_path / "2025-Q4.zip"
    # Both parts lack RCFD1773 entirely.
    part1 = "IDRSSD\tRCFD0211\n11111\t1\n"
    part2 = "IDRSSD\tRCONG349\n11111\t2\n"
    _make_zip(
        zip_path,
        {
            "FFIEC CDR Call Schedule RCB 12312025(1 of 2).txt": part1,
            "FFIEC CDR Call Schedule RCB 12312025(2 of 2).txt": part2,
        },
    )
    client = CdrClient(cache_dir=tmp_path)
    with pytest.raises(ValueError, match="missing required column"):
        list(
            client.iter_schedule_rows(
                "2025-Q4",
                "RCB",
                required_columns=(("RCFD1773",),),
            )
        )


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


def test_pick_first_non_empty_warns_on_divergent_candidates(caplog) -> None:
    """Empirically First-Citizens 2025-Q4 reports RCFD1773 == RCON1773 ==
    31790000. If a future quarter ships divergent values for the two
    candidates, surface a WARNING so the silent first-wins choice doesn't
    mask a real reporting discrepancy."""
    from peerbench.ingest.cdr import pick_first_non_empty

    row = {"IDRSSD": "12345", "RCFD1773": "31790000", "RCON1773": "31790001"}
    with caplog.at_level("WARNING", logger="peerbench.ingest.cdr"):
        result = pick_first_non_empty(row, ("RCFD1773", "RCON1773"))
    assert result == "31790000"
    assert any("Divergent" in rec.message for rec in caplog.records)


def test_pick_first_non_empty_silent_when_candidates_agree(caplog) -> None:
    """Equal non-empty candidates is the common case (e.g. First-Citizens
    both 31790000). Should NOT warn — only divergence is suspicious."""
    from peerbench.ingest.cdr import pick_first_non_empty

    row = {"IDRSSD": "12345", "RCFD1773": "31790000", "RCON1773": "31790000"}
    with caplog.at_level("WARNING", logger="peerbench.ingest.cdr"):
        result = pick_first_non_empty(row, ("RCFD1773", "RCON1773"))
    assert result == "31790000"
    assert not any("Divergent" in rec.message for rec in caplog.records)


def test_iter_schedule_rows_three_file_fan_in(tmp_path: Path) -> None:
    """If FFIEC ships RC-B as three files in a future quarter, only the
    member that satisfies the required column group should stream. Codex
    P2 regression coverage: (1 of 3) has IDRSSD only, (2 of 3) has both
    IDRSSD and the target MDRM, (3 of 3) has neither."""
    zip_path = tmp_path / "2025-Q4.zip"
    part1 = "IDRSSD\tRCFD0211\n11111\t1\n22222\t2\n"  # no RCFD1773
    part2 = "IDRSSD\tRCFD1773\n11111\t100\n22222\t200\n"  # the useful file
    part3 = "RCONG349\tRCONG350\n9\t8\n"  # no IDRSSD, no RCFD1773
    _make_zip(
        zip_path,
        {
            "FFIEC CDR Call Schedule RCB 12312025(1 of 3).txt": part1,
            "FFIEC CDR Call Schedule RCB 12312025(2 of 3).txt": part2,
            "FFIEC CDR Call Schedule RCB 12312025(3 of 3).txt": part3,
        },
    )
    client = CdrClient(cache_dir=tmp_path)
    rows = list(
        client.iter_schedule_rows(
            "2025-Q4",
            "RCB",
            required_columns=(("IDRSSD",), ("RCFD1773",)),
        )
    )
    assert len(rows) == 2
    assert {r["IDRSSD"] for r in rows} == {"11111", "22222"}
    assert {r["RCFD1773"] for r in rows} == {"100", "200"}


def test_coerce_cdr_value_roundtrips_decimal() -> None:
    """coerce_cdr_value is the single str -> Decimal coercion point for
    CDR-sourced facts. Returns None for blank/null markers; returns
    Decimal preserving precision for everything else."""
    from decimal import Decimal

    from peerbench.ingest.cdr import coerce_cdr_value

    assert coerce_cdr_value(None) is None
    assert coerce_cdr_value("") is None
    assert coerce_cdr_value("  ") is None
    assert coerce_cdr_value("NR") is None
    assert coerce_cdr_value("N/A") is None
    assert coerce_cdr_value("NA") is None
    assert coerce_cdr_value("NULL") is None
    assert coerce_cdr_value("null") is None
    assert coerce_cdr_value("31790000") == Decimal("31790000")
    assert coerce_cdr_value("1500000.42") == Decimal("1500000.42")
    # Non-numeric falls through to None rather than raising.
    assert coerce_cdr_value("not-a-number") is None


def test_iter_schedule_rows_required_columns_default_off(tmp_path: Path) -> None:
    """Empty `required_columns` keeps the old permissive behavior for
    callers that don't care to validate (today: tests + future probes)."""
    zip_path = tmp_path / "2025-Q4.zip"
    _make_zip(zip_path, {"FFIEC CDR Call Schedule RCRI 12312025.txt": _rcri_tsv()})
    client = CdrClient(cache_dir=tmp_path)
    rows = list(client.iter_schedule_rows("2025-Q4", "RCRI"))
    assert len(rows) == 3


_ = io  # keep `io` import referenced for future fixtures (e.g. encoding probes)
