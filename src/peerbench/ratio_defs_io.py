"""Read data/ratios.csv into typed Pydantic rows."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from peerbench.config import REPO_ROOT


class RatioDefRow(BaseModel):
    """One row of data/ratios.csv, validated."""

    model_config = ConfigDict(extra="forbid")

    ratio_id: str
    display_name: str
    category: str
    numerator_formula: str
    denominator_formula: str
    annualize: bool
    avg_or_eop: str
    fdic_precomputed_code: str | None = Field(default=None)
    ubpr_concept: str | None = Field(default=None)
    regulatory_threshold: dict[str, Any] | None = Field(default=None)
    suppress_when: dict[str, Any] | None = Field(default=None)
    notes: str | None = Field(default=None)

    @field_validator("annualize", mode="before")
    @classmethod
    def _coerce_bool(cls, v: object) -> bool:
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            lowered = v.strip().lower()
            if lowered in {"true", "1", "yes"}:
                return True
            if lowered in {"false", "0", "no", ""}:
                return False
        msg = f"invalid bool: {v!r}"
        raise ValueError(msg)

    @field_validator("avg_or_eop")
    @classmethod
    def _check_avg_or_eop(cls, v: str) -> str:
        if v not in {"AVG", "EOP"}:
            msg = f"avg_or_eop must be 'AVG' or 'EOP', got {v!r}"
            raise ValueError(msg)
        return v

    @field_validator(
        "fdic_precomputed_code",
        "ubpr_concept",
        "notes",
        mode="before",
    )
    @classmethod
    def _empty_to_none(cls, v: object) -> object:
        if isinstance(v, str) and v.strip() == "":
            return None
        return v

    @field_validator("regulatory_threshold", "suppress_when", mode="before")
    @classmethod
    def _parse_json(cls, v: object) -> object:
        if v is None or v == "":
            return None
        if isinstance(v, dict):
            return v
        if isinstance(v, str):
            stripped = v.strip()
            if not stripped:
                return None
            return json.loads(stripped)
        msg = f"expected JSON object or None, got {type(v).__name__}: {v!r}"
        raise ValueError(msg)


def _default_ratios_csv() -> Path:
    """Locate ratios.csv at runtime.

    Wheel install: hatch force-include ships the CSV at
    `<site-packages>/peerbench/_data/ratios.csv` (see pyproject.toml).
    Editable / dev install: `_data/` isn't created next to the source tree,
    so fall back to the repo-root data/ratios.csv.
    """
    packaged = Path(__file__).resolve().parent / "_data" / "ratios.csv"
    if packaged.is_file():
        return packaged
    return REPO_ROOT / "data" / "ratios.csv"


def load_ratio_defs(csv_path: Path | None = None) -> list[RatioDefRow]:
    path = csv_path or _default_ratios_csv()
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [RatioDefRow.model_validate(row) for row in reader]
