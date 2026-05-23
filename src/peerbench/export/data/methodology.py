"""Build the Methodology tab payload from ratio_defs + field-deps snapshot."""

from __future__ import annotations

from typing import Any, Protocol

from peerbench.export.data.types import (
    MethodologyBlock,
    MethodologyNote,
    MethodologyTab,
)


class RatioDefLike(Protocol):
    ratio_id: str
    display_name: str
    category: str
    numerator_formula: str
    denominator_formula: str
    annualize: bool
    avg_or_eop: str
    fdic_precomputed_code: str | None
    regulatory_threshold: dict[str, Any] | None
    notes: str | None


INTRO_NOTES: list[MethodologyNote] = [
    MethodologyNote(
        label="Data sources",
        text="FDIC BankFind API + FFIEC CDR bulk files.",
    ),
    MethodologyNote(
        label="Annualization",
        text="YTD income × 4/Qn for Q1–Q3; Q4 not annualized.",
    ),
    MethodologyNote(
        label="Tax-equivalent",
        text=(
            "Ratios reported on a non-TE basis. UBPR uses TE; expect 5–15 "
            "bps gap on NIM/yields depending on muni mix."
        ),
    ),
    MethodologyNote(
        label="Average vs period-end",
        text=("Per ratio_defs.avg_or_eop. AVG ratios use FDIC 5-period YTD averages."),
    ),
    MethodologyNote(
        label="CBLR filers",
        text=(
            "Small banks under the Community Bank Leverage Ratio framework "
            "do not report Tier 1 RBC / Total RBC / CET1. Those cells "
            "render em-dash and are excluded from quartile cutoffs."
        ),
    ),
    MethodologyNote(
        label="Restatement detector",
        text=(
            "Incoming FDIC values are compared to stored values; on diff, "
            "the fact is flagged restated, logged, and affected ratios are "
            "recomputed. Forward-quarter ratios that depend on 5-period "
            "averages are also flagged partial."
        ),
    ),
    MethodologyNote(
        label="Regulatory citations",
        text="SR 07-1, OCC Bulletin 2006-46, FIL-23-2023.",
    ),
]


def render_regulatory_threshold(payload: dict[str, Any] | None) -> str | None:
    if payload is None:
        return None
    amber = payload.get("amber_pct")
    red = payload.get("red_pct")
    citation = payload.get("citation", "")
    parts: list[str] = []
    if amber is not None:
        parts.append(f"Amber ≥ {amber}%")
    if red is not None:
        parts.append(f"Red ≥ {red}%")
    body = ", ".join(parts) if parts else "see citation"
    if citation:
        return f"{body} — {citation}"
    return body


def build_methodology(
    ratio_defs: list[RatioDefLike],
    *,
    field_deps: dict[str, list[str]],
) -> MethodologyTab:
    blocks: list[MethodologyBlock] = []
    for r in ratio_defs:
        blocks.append(
            MethodologyBlock(
                ratio_id=r.ratio_id,
                display_name=r.display_name,
                category=r.category,
                formula=f"{r.numerator_formula} / {r.denominator_formula}",
                source_fields=list(field_deps.get(r.ratio_id, [])),
                annualization=("YTD × 4/Qn" if r.annualize else "Not annualized"),
                basis=r.avg_or_eop,
                fdic_precomputed=r.fdic_precomputed_code,
                regulatory_threshold=render_regulatory_threshold(r.regulatory_threshold),
                notes=r.notes,
            )
        )
    return MethodologyTab(intro_notes=INTRO_NOTES, blocks=blocks)
