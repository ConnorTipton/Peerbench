"""Pure-function payload builder for the workbook manifest JSON."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def build_manifest(
    workbook_path: Path,
    *,
    anchor_cert: int,
    quarter_id: str,
    public_url_base: str,
) -> dict[str, Any]:
    """Build the manifest JSON dict for the dashboard to consume.

    The dashboard reads `latest.json` from the same Supabase Storage bucket
    that holds `latest.xlsx`; this builder is the single source of truth for
    the manifest shape.
    """
    base = public_url_base.rstrip("/")
    return {
        "url": f"{base}/latest.xlsx",
        "generated_at": datetime.now(UTC).isoformat(),
        "quarter_id": quarter_id,
        "anchor_cert": anchor_cert,
        "size_bytes": workbook_path.stat().st_size,
    }
