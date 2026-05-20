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

Conventions
-----------
- **Per-quarter cache** at `cache/cdr/YYYY-Qn.zip`. Directory is gitignored.
- **CDR field codes are namespaced.** Values written to `facts.field_code`
  use a `CDR_*` prefix (see `peerbench.fdic_fields.CDR_FIELDS`). The MDRM
  column names *inside* the TSV change across quarters and are resolved
  through `peerbench.ingest.cdr_schema.cdr_column()`.
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
        required_columns: tuple[str, ...] = (),
    ) -> Iterator[dict[str, str]]:
        """Stream rows from the first inner file matching schedule_pattern.

        Memory-safe: opens the inner file via `zipfile.open()` and iterates
        line-by-line. Yields one dict per row keyed by the TSV header
        (MDRM codes). Values stay as raw strings — callers convert.

        If `required_columns` is non-empty, the first row's header is
        checked against it; a missing column raises ValueError so that
        domain-prefix drift (RCON/RCOA/RCFD) or unexpected header layout
        fails loudly instead of silently producing zero matches.
        """
        zip_path = self.get_zip_path(quarter_id)
        with zipfile.ZipFile(zip_path) as zf:
            member = self._find_member(zf, schedule_pattern)
            logger.info("CDR streaming %s :: %s", zip_path.name, member)
            with zf.open(member) as raw:
                text = io.TextIOWrapper(raw, encoding="utf-8-sig", newline="")
                reader = csv.DictReader(text, delimiter="\t")
                header_validated = not required_columns
                for row in reader:
                    if not header_validated:
                        missing = [c for c in required_columns if c not in row]
                        if missing:
                            seen = sorted(row.keys())
                            msg = (
                                f"Schedule {member!r} is missing required "
                                f"column(s) {missing}; header had "
                                f"{len(seen)} column(s) (first 10: {seen[:10]})"
                            )
                            raise ValueError(msg)
                        header_validated = True
                    yield row

    @staticmethod
    def _find_member(zf: zipfile.ZipFile, schedule_pattern: str) -> str:
        names = zf.namelist()
        # Word-boundary match: "RCRI" must not match "RCRII" (Part II);
        # FFIEC ZIPs ship both Part I and Part II files. \b treats the
        # alphanumeric/non-alphanumeric transition as the token edge.
        token = re.compile(rf"\b{re.escape(schedule_pattern)}\b")
        candidates = [n for n in names if token.search(n)]
        if not candidates:
            preview = names[:5]
            msg = (
                f"No file matching pattern {schedule_pattern!r} inside ZIP "
                f"(saw {len(names)} member(s); first 5: {preview})"
            )
            raise ValueError(msg)
        if len(candidates) > 1:
            logger.warning(
                "Multiple files match %r — picking first: %s (others: %s)",
                schedule_pattern,
                candidates[0],
                candidates[1:],
            )
        return candidates[0]
