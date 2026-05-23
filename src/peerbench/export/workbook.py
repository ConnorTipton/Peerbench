"""Workbook orchestration: pull DB rows, build typed payloads, write file."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from peerbench.db import Fact, Institution, QualityLog, Quarter, Ratio, RatioDef
from peerbench.export.data.comp_sheet import build_comp_sheets
from peerbench.export.data.cover import build_cover
from peerbench.export.data.methodology import build_methodology
from peerbench.export.data.restatement import build_restatement_log
from peerbench.export.data.summary import build_summary
from peerbench.export.data.time_series import build_time_series
from peerbench.export.data.types import WorkbookBundle
from peerbench.export.writer import write_workbook

REPO_ROOT = Path(__file__).resolve().parents[3]
FIELD_DEPS_PATH = REPO_ROOT / "web" / "lib" / "ratio-field-deps.generated.json"

TIME_SERIES_WINDOW = 8


def run_export(
    session: Session,
    *,
    anchor_cert: int,
    quarter_id: str,
    out_dir: Path,
) -> Path:
    """Generate the Phase 4.2 comp workbook; return the path written.

    Raises ValueError on unknown anchor or quarter.
    """
    quarter = session.get(Quarter, quarter_id)
    if quarter is None:
        recent = session.scalars(
            select(Quarter.quarter_id).order_by(Quarter.quarter_id.desc()).limit(8)
        ).all()
        raise ValueError(f"unknown quarter_id={quarter_id!r}; recent: {list(recent)}")
    anchor = session.get(Institution, anchor_cert)
    if anchor is None:
        raise ValueError(f"unknown anchor cert={anchor_cert}")

    peers = list(
        session.scalars(
            select(Institution).where(
                Institution.active.is_(True),
                Institution.cert != anchor_cert,
            )
        ).all()
    )
    peers.sort(key=lambda i: i.name)

    window_quarters = list(
        session.scalars(
            select(Quarter.quarter_id)
            .where(Quarter.quarter_id <= quarter_id)
            .order_by(Quarter.quarter_id.desc())
            .limit(TIME_SERIES_WINDOW)
        ).all()
    )
    window_quarters.sort()
    income_statement_quarters = (
        window_quarters[-4:] if len(window_quarters) >= 4 else window_quarters
    )

    cert_set = {anchor_cert, *(p.cert for p in peers)}

    ratio_rows_window = list(
        session.execute(
            select(
                Ratio.cert,
                Ratio.quarter_id,
                Ratio.ratio_id,
                Ratio.value,
                Ratio.data_quality,
            )
            .where(Ratio.cert.in_(cert_set))
            .where(Ratio.quarter_id.in_(window_quarters))
        ).all()
    )
    ratios_for_quarter: dict[int, dict[str, Decimal | None]] = {c: {} for c in cert_set}
    ratios_full: dict[int, dict[tuple[str, str], Decimal | None]] = {c: {} for c in cert_set}
    suppressed: set[tuple[int, str]] = set()
    for cert, qid, rid, value, dq in ratio_rows_window:
        ratios_full[cert][(qid, rid)] = value
        if qid == quarter_id:
            ratios_for_quarter[cert][rid] = value
            if dq == "suppressed":
                suppressed.add((cert, rid))

    fact_quarters = set(income_statement_quarters) | {quarter_id}
    fact_rows = list(
        session.execute(
            select(Fact.cert, Fact.quarter_id, Fact.field_code, Fact.value)
            .where(Fact.cert.in_(cert_set))
            .where(Fact.quarter_id.in_(fact_quarters))
        ).all()
    )
    facts: dict[tuple[int, str], dict[str, Decimal | None]] = {}
    for cert, qid, code, value in fact_rows:
        facts.setdefault((cert, qid), {})[code] = value

    ratio_defs = list(session.scalars(select(RatioDef)).all())
    field_deps = json.loads(FIELD_DEPS_PATH.read_text(encoding="utf-8"))

    restatement_events = [
        {
            "detected_at": ev.detected_at,
            "cert": ev.cert,
            "quarter_id": ev.quarter_id,
            "field_code": ev.field_code,
            "old_value": ev.old_value,
            "new_value": ev.new_value,
        }
        for ev in session.scalars(
            select(QualityLog).where(QualityLog.event_type == "restated")
        ).all()
        if ev.cert in cert_set
    ]
    bank_names = {anchor_cert: anchor.name, **{p.cert: p.name for p in peers}}

    anchor_pair = (anchor_cert, anchor.name)
    peer_pairs = [(p.cert, p.name) for p in peers]

    cover = build_cover(
        anchor_cert=anchor_cert,
        anchor_name=anchor.name,
        quarter_id=quarter_id,
        quarter_end_date=quarter.report_date,
        generated_at=datetime.now(UTC),
        data_vintage=quarter.ingest_at,
        anchor_has_no_ratios=not ratios_for_quarter.get(anchor_cert),
        active_peer_count=len(peers),
    )
    summary = build_summary(
        anchor=anchor_pair,
        peers=peer_pairs,
        ratio_defs=ratio_defs,  # type: ignore[arg-type]
        ratios_by_cert=ratios_for_quarter,
        suppressed=suppressed,
    )
    comp_sheets = build_comp_sheets(
        anchor=anchor_pair,
        peers=peer_pairs,
        quarter_id=quarter_id,
        income_statement_quarter_ids=income_statement_quarters,
        facts_by_cert_quarter=facts,
        ratios_by_cert=ratios_for_quarter,
        ratio_defs=ratio_defs,  # type: ignore[arg-type]
    )
    time_series = build_time_series(
        anchor=anchor_pair,
        peers=peer_pairs,
        quarter_ids=window_quarters,
        ratios_by_cert_quarter=ratios_full,
        ratio_defs=ratio_defs,  # type: ignore[arg-type]
    )
    restatement_log = build_restatement_log(
        restatement_events,
        bank_names=bank_names,
        field_deps=field_deps,
        window=set(window_quarters),
    )
    methodology = build_methodology(ratio_defs, field_deps=field_deps)  # type: ignore[arg-type]

    bundle = WorkbookBundle(
        cover=cover,
        summary=summary,
        comp_sheets=comp_sheets,
        time_series=time_series,
        restatement_log=restatement_log,
        methodology=methodology,
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"peerbench_{anchor_cert}_{quarter_id}.xlsx"
    write_workbook(bundle, out_path)
    return out_path
