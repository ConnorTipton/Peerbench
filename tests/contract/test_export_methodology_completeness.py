"""Contract: every ratio in data/ratios.csv yields a methodology block."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from peerbench.export.data.methodology import build_methodology
from peerbench.ratio_defs_io import load_ratio_defs

REPO_ROOT = Path(__file__).resolve().parents[2]
FIELD_DEPS_PATH = REPO_ROOT / "web" / "lib" / "ratio-field-deps.generated.json"


@pytest.mark.contract
def test_methodology_covers_every_ratio() -> None:
    csv_rows = load_ratio_defs()
    field_deps = json.loads(FIELD_DEPS_PATH.read_text(encoding="utf-8"))
    tab = build_methodology(list(csv_rows), field_deps=field_deps)
    csv_ids = {r.ratio_id for r in csv_rows}
    block_ids = {b.ratio_id for b in tab.blocks}
    assert csv_ids == block_ids
