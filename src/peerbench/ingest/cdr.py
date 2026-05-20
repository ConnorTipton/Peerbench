"""FFIEC CDR (Call Report) bulk-file ingest client.

The FDIC BankFind API does not expose every field the ratio engine needs;
two ratios (`cet1`, `htm_loss_t1`) require fields from the FFIEC CDR Subject
Data Format ZIPs. This module reads those ZIPs from a local cache and
streams the relevant schedule TSVs row-by-row — never reading the
multi-hundred-MB inner files into memory.

Cache-first design (manual download required)
---------------------------------------------
The FFIEC public bulk-download page (cdr.ffiec.gov/CDR/Public/CDRDownload.aspx)
requires interactive form submission (ASP.NET VIEWSTATE + cookies) and
cannot be automated with a plain HTTP GET. Rather than ship a brittle
Selenium-class scraper, this client expects ZIPs to be staged manually at
`cache/cdr/YYYY-Qn.zip`. `get_zip_path()` raises `CdrZipNotCached` with
explicit instructions when a ZIP is missing.

Multi-file and multi-domain semantics
-------------------------------------
FFIEC ships some schedules split across multiple files (e.g. RC-B as
`Schedule RCB 12312025(1 of 2).txt` + `(2 of 2).txt`). `iter_schedule_rows`
finds ALL members matching the schedule pattern and chains their row
iterators so no bank is silently dropped.

Some MDRMs appear under multiple domain prefixes within a single quarter:
RC-R amounts use `RCOA*` for domestic-only filers and `RCFA*` for filers
with foreign offices. The schema map exposes candidate tuples and callers
use `pick_first_non_empty` to resolve a single value per row.

Conventions
-----------
- **Per-quarter cache** at `cache/cdr/YYYY-Qn.zip`. Directory is gitignored.
- **CDR field codes are namespaced.** Values written to `facts.field_code`
  use a `CDR_*` prefix (see `peerbench.fdic_fields.CDR_FIELDS`). The MDRM
  column names *inside* the TSV change across quarters and are resolved
  through `peerbench.ingest.cdr_schema.cdr_columns()`.
- **Quarter row reuse.** CDR-sourced facts piggyback on the existing
  `quarters` row created by the FDIC API ingest. See the known-tech-debt
  entry in `docs/divergences.md`.
- **RSSD-keyed rows.** CDR TSVs identify banks by RSSD ID (column
  `IDRSSD`), not FDIC Cert. Callers map RSSD → Cert via
  `institutions.rssd` (or by reading the cached RSSDID fact).
"""

from __future__ import annotations

import csv
import io
import logging
import re
import zipfile
from collections.abc import Iterator
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_CACHE_DIR = Path("cache/cdr")
RSSD_COLUMN = "IDRSSD"
FFIEC_DOWNLOAD_URL = "https://cdr.ffiec.gov/CDR/Public/CDRDownload.aspx"


class CdrZipNotCachedError(FileNotFoundError):
    """Raised when no cached ZIP exists for the requested quarter.

    Message includes the expected path and manual-download instructions.
    """


def pick_first_non_empty(row: dict[str, str], columns: tuple[str, ...]) -> str | None:
    """Return the first non-empty value across `columns`, else None.

    Used by ingest-cdr to resolve a single MDRM value across the candidate
    tuple from `cdr_schema.cdr_columns()`. Treats whitespace-only strings
    as empty. Order is preference: callers list the more-common candidate
    first (e.g. RCOA before RCFA for CET1 because the domestic-only
    population is larger).
    """
    for col in columns:
        v = row.get(col)
        if v is None:
            continue
        s = v.strip()
        if s:
            return v
    return None


class CdrClient:
    """Reads FFIEC CDR Subject Data Format ZIPs from a local cache.

    Pure read-side: no HTTP. ZIPs must be staged manually (see module
    docstring). The streaming parser is encoding-aware (UTF-8 with BOM)
    and yields raw string values; Decimal coercion is the caller's job
    so the parser stays format-agnostic and unit-testable.
    """

    def __init__(self, cache_dir: Path | None = None) -> None:
        self._cache_dir = cache_dir or DEFAULT_CACHE_DIR

    @property
    def cache_dir(self) -> Path:
        return self._cache_dir

    def get_zip_path(self, quarter_id: str) -> Path:
        """Return the cached ZIP path; raise CdrZipNotCachedError if missing."""
        path = self._cache_dir / f"{quarter_id}.zip"
        if not path.exists():
            msg = (
                f"FFIEC CDR ZIP not in cache: {path}\n"
                f"Manual download required — FFIEC's public bulk endpoint "
                f"is a form-driven ASP.NET app and cannot be reached with a "
                f"plain HTTP GET.\n"
                f"  1. Visit {FFIEC_DOWNLOAD_URL}\n"
                f"  2. Select 'Subject Data Format' and quarter {quarter_id}\n"
                f"  3. Save the resulting ZIP to: {path.resolve()}"
            )
            raise CdrZipNotCachedError(msg)
        return path

    def iter_schedule_rows(
        self,
        quarter_id: str,
        schedule_pattern: str,
        required_columns: tuple[tuple[str, ...], ...] = (),
    ) -> Iterator[dict[str, str]]:
        """Stream rows from every inner file matching `schedule_pattern`.

        Memory-safe: opens each inner file via `zipfile.open()` and iterates
        line-by-line. Yields one dict per row keyed by the TSV header
        (MDRM codes). Values stay as raw strings — callers convert.

        `required_columns` is a tuple of candidate groups; each group must
        be satisfied (by at least one column present in the file header)
        for that file's rows to be streamed. Use this to catch domain-
        prefix drift (RCON/RCOA/RCFD) without rejecting populations where
        only one of two candidates is present (e.g. `RCOAP859` for
        domestic-only banks, `RCFAP859` for foreign-office banks —
        `required_columns=(("RCOAP859", "RCFAP859"),)` passes for either
        population but fails if neither is in any candidate member).

        Multi-file schedules (e.g. RC-B 2025-Q4 ships as `(1 of 2).txt` +
        `(2 of 2).txt` with disjoint MDRM sets) are handled by per-member
        skipping: members lacking the required columns are skipped, others
        contribute their rows. If NO matching member satisfies the groups,
        the parser raises `ValueError` so layout drift surfaces loudly.

        Empty `required_columns` performs no header check; all matching
        members are streamed unconditionally.
        """
        zip_path = self.get_zip_path(quarter_id)
        with zipfile.ZipFile(zip_path) as zf:
            members = self._find_members(zf, schedule_pattern)
            logger.info(
                "CDR streaming %s :: %d member(s) matching %r",
                zip_path.name,
                len(members),
                schedule_pattern,
            )
            any_streamed = False
            skipped: list[tuple[str, list[tuple[str, ...]]]] = []
            for member in members:
                with zf.open(member) as raw:
                    text = io.TextIOWrapper(raw, encoding="utf-8-sig", newline="")
                    reader = csv.DictReader(text, delimiter="\t")
                    fieldnames = reader.fieldnames or []
                    if required_columns:
                        missing_groups = [
                            grp for grp in required_columns if not any(c in fieldnames for c in grp)
                        ]
                        if missing_groups:
                            logger.info(
                                "  skipping member (missing %s): %s",
                                missing_groups,
                                member,
                            )
                            skipped.append((member, missing_groups))
                            continue
                    logger.info("  member: %s", member)
                    any_streamed = True
                    yield from reader
            if required_columns and not any_streamed:
                detail = (
                    "; ".join(f"{m!r} missing {grps}" for m, grps in skipped)
                    or "no matching members in ZIP"
                )
                msg = (
                    f"No member matching {schedule_pattern!r} in "
                    f"{zip_path.name} had all required column group(s) "
                    f"{list(required_columns)} — missing required column(s) "
                    f"in every candidate. Tried: {detail}"
                )
                raise ValueError(msg)

    @staticmethod
    def _find_members(zf: zipfile.ZipFile, schedule_pattern: str) -> list[str]:
        """Return all member names matching `schedule_pattern` as a whole
        token. RCB Memorandum 2 ships split across `(1 of 2).txt` and
        `(2 of 2).txt`; both must stream. Word-boundary keeps RCRI distinct
        from RCRII."""
        names = zf.namelist()
        token = re.compile(rf"\b{re.escape(schedule_pattern)}\b")
        candidates = [n for n in names if token.search(n)]
        if not candidates:
            preview = names[:5]
            msg = (
                f"No file matching pattern {schedule_pattern!r} inside ZIP "
                f"(saw {len(names)} member(s); first 5: {preview})"
            )
            raise ValueError(msg)
        return sorted(candidates)
