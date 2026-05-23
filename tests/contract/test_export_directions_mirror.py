"""Contract: peerbench.export.directions must mirror web/lib/heatmap-directions.ts.

The TS file is canonical (backs the dashboard heat map). The Python copy
backs the Excel export. Both must agree on direction for every ratio.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from peerbench.export.directions import RATIO_DIRECTIONS

REPO_ROOT = Path(__file__).resolve().parents[2]
TS_PATH = REPO_ROOT / "web" / "lib" / "heatmap-directions.ts"

LINE_RE = re.compile(
    r'^\s*([a-z_][a-z0-9_]*):\s*"(higher_is_positive|higher_is_negative|neutral)"',
    re.MULTILINE,
)


@pytest.mark.contract
def test_directions_mirror_matches_typescript_source() -> None:
    text = TS_PATH.read_text(encoding="utf-8")
    ts_entries = dict(LINE_RE.findall(text))
    assert ts_entries, "regex failed to extract entries from heatmap-directions.ts"
    py_entries = dict(RATIO_DIRECTIONS)

    only_in_py = set(py_entries) - set(ts_entries)
    only_in_ts = set(ts_entries) - set(py_entries)
    mismatched = {
        k: (py_entries[k], ts_entries[k])
        for k in set(py_entries) & set(ts_entries)
        if py_entries[k] != ts_entries[k]
    }

    assert not only_in_py, f"Python has extra: {only_in_py}"
    assert not only_in_ts, f"TS has entries Python is missing: {only_in_ts}"
    assert not mismatched, f"direction mismatches: {mismatched}"
