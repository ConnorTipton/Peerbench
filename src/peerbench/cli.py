"""Peerbench CLI.

Commands:
  peerbench seed-ratios        — Upsert data/ratios.csv into the ratio_defs table.
  peerbench ingest             — Fetch FDIC API facts for a bank-quarter.
  peerbench ingest-cdr         — Read FFIEC CDR ZIPs and upsert CDR_* fields.
  peerbench compute            — Compute ratios for a bank-quarter and persist.
  peerbench info               — Quick sanity dump of registry + config.
  peerbench export             — Generate the Phase 4.2 Excel comp workbook.
  peerbench export-field-deps  — Regenerate the handler field-dependency JSON.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from peerbench.config import get_settings
from peerbench.db import Fact, Institution, Quarter, RatioDef, get_session
from peerbench.db.ratio_writer import upsert_ratio
from peerbench.fdic_fields import all_field_codes, all_fields
from peerbench.ingest import FdicClient, make_quality_log_callback, upsert_fact
from peerbench.ingest.cdr import (
    RSSD_COLUMN,
    CdrClient,
    CdrZipNotCachedError,
    coerce_cdr_value,
    pick_first_non_empty,
)
from peerbench.ingest.cdr_schema import SCHEDULE_PATTERN, cdr_columns, known_labels
from peerbench.quarters import (
    parse_quarter_id,
    quarter_end_date,
    recent_finalized_quarters,
)
from peerbench.ratio_defs_io import load_ratio_defs
from peerbench.ratio_engine import registered_handlers
from peerbench.ratio_engine.compute import (
    OkResult,
    PartialResult,
    SuppressedResult,
    compute_all_for_bank_quarter,
    load_fact_view,
)
from peerbench.validate import compare_to_fdic, evaluate_gate, format_table, write_snapshot

app = typer.Typer(no_args_is_help=True, add_completion=False)


@app.command("seed-ratios")
def seed_ratios() -> None:
    """Read data/ratios.csv and upsert into the ratio_defs table.

    Enforces 1:1 correspondence with the handler registry — refuses to seed
    if any ratio_id in the CSV has no handler, or any handler has no row.
    """
    rows = load_ratio_defs()
    handlers = registered_handlers()
    csv_ids = {r.ratio_id for r in rows}
    handler_ids = set(handlers.keys())
    missing_handlers = sorted(csv_ids - handler_ids)
    missing_csv_rows = sorted(handler_ids - csv_ids)
    if missing_handlers:
        typer.echo(f"CSV has ratios with no handler: {missing_handlers}", err=True)
        raise typer.Exit(code=2)
    if missing_csv_rows:
        typer.echo(f"Handlers with no CSV row: {missing_csv_rows}", err=True)
        raise typer.Exit(code=2)

    with get_session() as session:
        for row in rows:
            stmt = pg_insert(RatioDef).values(
                ratio_id=row.ratio_id,
                display_name=row.display_name,
                category=row.category,
                numerator_formula=row.numerator_formula,
                denominator_formula=row.denominator_formula,
                annualize=row.annualize,
                avg_or_eop=row.avg_or_eop,
                fdic_precomputed_code=row.fdic_precomputed_code,
                ubpr_concept=row.ubpr_concept,
                regulatory_threshold=row.regulatory_threshold,
                suppress_when=row.suppress_when,
                notes=row.notes,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["ratio_id"],
                set_={
                    "display_name": stmt.excluded.display_name,
                    "category": stmt.excluded.category,
                    "numerator_formula": stmt.excluded.numerator_formula,
                    "denominator_formula": stmt.excluded.denominator_formula,
                    "annualize": stmt.excluded.annualize,
                    "avg_or_eop": stmt.excluded.avg_or_eop,
                    "fdic_precomputed_code": stmt.excluded.fdic_precomputed_code,
                    "ubpr_concept": stmt.excluded.ubpr_concept,
                    "regulatory_threshold": stmt.excluded.regulatory_threshold,
                    "suppress_when": stmt.excluded.suppress_when,
                    "notes": stmt.excluded.notes,
                },
            )
            session.execute(stmt)
        total = session.scalar(select(RatioDef).order_by(RatioDef.ratio_id))
    typer.echo(
        f"seeded {len(rows)} ratio_defs rows; sample row PK: {total.ratio_id if total else 'none'}"
    )


def _ensure_quarter(session, qid: str, source: str) -> None:
    existing = session.get(Quarter, qid)
    year, quarter = parse_quarter_id(qid)
    if existing is None:
        session.add(
            Quarter(
                quarter_id=qid,
                year=year,
                quarter=quarter,
                report_date=quarter_end_date(year, quarter),
                ingest_at=datetime.now(UTC),
                source=source,
            )
        )


def _ensure_institution(session, cert: int, client: FdicClient) -> None:
    existing = session.get(Institution, cert)
    if existing is not None:
        return
    payload = client._get(
        "/institutions",
        {
            "filters": f"CERT:{cert}",
            "fields": "CERT,NAMEFULL,STALP,CITY,ACTIVE",
            "limit": 1,
            "format": "json",
        },
    )
    records = payload.get("data") or []
    if not records:
        msg = f"FDIC has no institution row for CERT {cert}"
        raise RuntimeError(msg)
    row = records[0].get("data") or records[0]
    session.add(
        Institution(
            cert=cert,
            name=str(row.get("NAMEFULL") or f"CERT {cert}"),
            state=str(row.get("STALP")) if row.get("STALP") else None,
            hq_city=str(row.get("CITY")) if row.get("CITY") else None,
            active=str(row.get("ACTIVE", "1")) == "1",
        )
    )


@app.command("ingest")
def ingest(
    cert: Annotated[int, typer.Option("--cert", help="FDIC certificate number")],
    quarters: Annotated[int, typer.Option("--quarters", help="How many most-recent quarters")] = 1,
) -> None:
    """Fetch FDIC API facts for one bank across N most-recent finalized quarters."""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    qids = recent_finalized_quarters(quarters)
    fields = list(all_fields())
    typer.echo(f"ingesting cert={cert} quarters={qids} fields={len(fields)}")
    with FdicClient() as client, get_session() as session:
        _ensure_institution(session, cert, client)
        on_diff = make_quality_log_callback(session)
        written = 0
        for qid in qids:
            _ensure_quarter(session, qid, source="fdic_api")
            data = client.financials(cert, qid, fields)
            for field_code, value in data.items():
                # Skip the wasteful "no row and no value" case, but always
                # upsert when an existing fact transitions to/from NULL —
                # that's a restatement the detector must catch.
                if value is None and session.get(Fact, (cert, qid, field_code)) is None:
                    continue
                upsert_fact(session, cert, qid, field_code, value, on_diff=on_diff)
                written += 1
            typer.echo(
                f"  {qid}: {sum(1 for v in data.values() if v is not None)} fields with values"
            )
    typer.echo(f"done: {written} fact upserts across {len(qids)} quarter(s)")


_CDR_FIELD_CODE: dict[str, str] = {
    "CET1_CAPITAL": "CDR_CET1_CAPITAL",
    "HTM_FAIRVAL": "CDR_HTM_FAIRVAL",
}


def _parse_cert_list(certs: str) -> list[int]:
    return [int(c.strip()) for c in certs.split(",") if c.strip()]


@app.command("ingest-cdr")
def ingest_cdr(
    certs: Annotated[str, typer.Option("--certs", help="Comma-separated FDIC cert numbers")],
    quarters: Annotated[int, typer.Option("--quarters", help="How many most-recent quarters")] = 1,
) -> None:
    """Ingest FFIEC CDR fields (CET1 capital, HTM fair value) into `facts`.

    Reads cached Subject Data Format ZIPs from `cache/cdr/YYYY-Qn.zip`. The
    FFIEC bulk endpoint is form-driven and not auto-downloadable; if a ZIP
    is missing, the client raises with manual-download instructions.

    Requires `peerbench ingest` to have been run first so the `RSSDID` fact
    is populated — CDR rows are keyed by RSSD, and we map back to Cert.
    """
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    cert_list = _parse_cert_list(certs)
    qids = recent_finalized_quarters(quarters)
    typer.echo(f"ingest-cdr certs={cert_list} quarters={qids}")

    client = CdrClient()
    with get_session() as session:
        rssd_rows = session.execute(
            select(Fact.cert, Fact.value)
            .where(Fact.field_code == "RSSDID")
            .where(Fact.cert.in_(cert_list))
        ).all()
        cert_for_rssd: dict[int, int] = {}
        for cert_val, value in rssd_rows:
            if value is None:
                continue
            cert_for_rssd[int(value)] = cert_val
        missing = set(cert_list) - set(cert_for_rssd.values())
        if missing:
            typer.echo(
                f"Missing RSSDID in facts for certs: {sorted(missing)}. "
                f"Run `peerbench ingest --cert <N>` first.",
                err=True,
            )
            raise typer.Exit(code=2)

        on_diff = make_quality_log_callback(session)
        upsert_count = 0
        for qid in qids:
            _ensure_quarter(session, qid, source="ffiec_cdr")
            for label in known_labels():
                pattern = SCHEDULE_PATTERN[label]
                candidates = cdr_columns(qid, label)
                field_code = _CDR_FIELD_CODE[label]
                seen = 0
                matched_certs: set[int] = set()
                try:
                    rows = client.iter_schedule_rows(
                        qid,
                        pattern,
                        required_columns=((RSSD_COLUMN,), candidates),
                    )
                    for row in rows:
                        seen += 1
                        rssd_raw = row.get(RSSD_COLUMN)
                        if not rssd_raw:
                            continue
                        try:
                            rssd = int(rssd_raw.strip())
                        except ValueError:
                            continue
                        cert_val = cert_for_rssd.get(rssd)
                        if cert_val is None:
                            continue
                        raw_value = pick_first_non_empty(row, candidates)
                        value = coerce_cdr_value(raw_value)
                        if value is None and session.get(Fact, (cert_val, qid, field_code)) is None:
                            continue
                        upsert_fact(session, cert_val, qid, field_code, value, on_diff=on_diff)
                        upsert_count += 1
                        matched_certs.add(cert_val)
                except CdrZipNotCachedError as e:
                    typer.echo(str(e), err=True)
                    raise typer.Exit(code=2) from None
                except ValueError as e:
                    typer.echo(f"CDR schedule layout error for {qid} {label}: {e}", err=True)
                    raise typer.Exit(code=2) from None
                typer.echo(
                    f"  {qid} {label}: {len(matched_certs)}/{len(cert_list)} certs matched "
                    f"({seen} rows scanned, candidates={list(candidates)})"
                )
                missing_certs = set(cert_list) - matched_certs
                if missing_certs:
                    typer.echo(
                        f"    WARN: certs missing from {qid} {label}: "
                        f"{sorted(missing_certs)} — downstream ratios will be "
                        f"marked partial.",
                        err=True,
                    )
    typer.echo(f"done: {upsert_count} CDR fact upserts")


@app.command("compute")
def compute(
    cert: Annotated[int, typer.Option("--cert", help="FDIC certificate number")],
    quarters: Annotated[
        int, typer.Option("--quarters", help="How many most-recent quarters to compute")
    ] = 1,
) -> None:
    """Compute ratios for one bank across N most-recent finalized quarters.

    Reads `facts` for each (cert, quarter_id) plus the 4 preceding quarters
    (5-period YTD averaging per FDIC convention), dispatches every ratio in
    `ratio_defs`, and upserts the resulting Decimal/data_quality into the
    `ratios` table.
    """
    qids = recent_finalized_quarters(quarters)
    typer.echo(f"computing cert={cert} quarters={qids}")
    handlers = registered_handlers()
    with get_session() as session:
        ratio_defs = list(session.scalars(select(RatioDef)).all())
        if not ratio_defs:
            typer.echo("no ratio_defs rows — run `peerbench seed-ratios` first.", err=True)
            raise typer.Exit(code=2)
        for qid in qids:
            fact_view = load_fact_view(session, cert, qid, periods=5)
            results = compute_all_for_bank_quarter(ratio_defs, fact_view)
            for rid, result in results.items():
                handler = handlers.get(rid)
                version = handler.version if handler is not None else "unknown"
                upsert_ratio(session, cert, qid, rid, result, version)
            ok = sum(1 for r in results.values() if isinstance(r, OkResult))
            partial = sum(1 for r in results.values() if isinstance(r, PartialResult))
            sup = sum(1 for r in results.values() if isinstance(r, SuppressedResult))
            typer.echo(f"  {qid}: {ok} ok, {partial} partial, {sup} suppressed")
    typer.echo("done")


@app.command("validate")
def validate(
    certs: Annotated[
        str,
        typer.Option(
            "--certs",
            help="Comma-separated FDIC cert numbers (default: 5-bank Phase 1 slice)",
        ),
    ] = "4063,4214,110,11063,5510",
    quarters: Annotated[
        int, typer.Option("--quarters", help="How many most-recent finalized quarters")
    ] = 8,
    write_snapshot_to: Annotated[
        str | None,
        typer.Option("--write-snapshot", help="Path to write the snapshot markdown"),
    ] = None,
) -> None:
    """Compare computed ratios against FDIC pre-computed; report basis-point diffs.

    DoD bar (Phase 1): mean abs <2 bps, max <5 bps across all OK-classified
    ratios with a mapped FDIC pre-computed code.
    """
    cert_list = [int(c.strip()) for c in certs.split(",") if c.strip()]
    qids = recent_finalized_quarters(quarters)
    typer.echo(f"validating certs={cert_list} quarters={qids}")
    with get_session() as session:
        comparisons, exclusions = compare_to_fdic(session, cert_list, qids)
    typer.echo(format_table(comparisons))
    typer.echo(
        f"\nExcluded: {exclusions.no_fdic_code} no-FDIC-code, "
        f"{exclusions.not_ok_quality} not-ok, "
        f"{exclusions.missing_fdic_fact} missing-FDIC-fact, "
        f"{exclusions.missing_ratio_row} missing-ratio-row"
    )
    gate, mean, mx = evaluate_gate(comparisons, exclusions)
    typer.echo(f"\nGate: {gate}  (N={len(comparisons)}, mean={mean:.2f} bps, max={mx:.2f} bps)")
    if write_snapshot_to:
        write_snapshot(
            comparisons,
            exclusions,
            Path(write_snapshot_to),
            certs=cert_list,
            quarter_ids=qids,
        )
        typer.echo(f"wrote snapshot to {write_snapshot_to}")
    if gate.startswith("FAIL"):
        raise typer.Exit(code=1)


def _resolve_latest_quarter_id(session: Session) -> str:
    """Return MAX(quarters.quarter_id). Raises ValueError if the table is empty.

    Correctness relies on quarter_id following the 'YYYY-Qn' format (e.g.
    '2025-Q4'), where lexicographic order coincides with chronological order.
    """
    latest = session.scalar(select(func.max(Quarter.quarter_id)))
    if latest is None:
        raise ValueError("no quarters in DB — run `peerbench ingest` first")
    return latest


@app.command("export")
def export_cmd(
    quarter: Annotated[
        str,
        typer.Option("--quarter", help="Quarter ID 'YYYY-Qn' (e.g. 2025-Q4) or 'latest'"),
    ],
    output: Annotated[
        Path,
        typer.Option("--output", help="Output directory; created if missing"),
    ],
    anchor: Annotated[
        int,
        typer.Option("--anchor", help="FDIC certificate number"),
    ] = 4063,
) -> None:
    """Generate the Phase 4.2 Excel comp workbook for an anchor × quarter."""
    from peerbench.export import run_export

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    if output.exists() and output.is_file():
        typer.echo(f"--output must be a directory, not a file: {output}", err=True)
        raise typer.Exit(code=2)
    with get_session() as session:
        try:
            resolved_quarter = (
                _resolve_latest_quarter_id(session) if quarter == "latest" else quarter
            )
            out_path = run_export(
                session,
                anchor_cert=anchor,
                quarter_id=resolved_quarter,
                out_dir=output,
            )
        except ValueError as e:
            typer.echo(str(e), err=True)
            raise typer.Exit(code=2) from None
    typer.echo(f"wrote {out_path}")


@app.command("upload-workbook")
def upload_workbook_cmd(
    file: Annotated[
        Path,
        typer.Option("--file", help="Path to the .xlsx file emitted by `peerbench export`"),
    ],
    anchor: Annotated[
        int,
        typer.Option("--anchor", help="FDIC certificate number"),
    ] = 4063,
    bucket: Annotated[
        str,
        typer.Option("--bucket", help="Supabase Storage bucket name"),
    ] = "peerbench-exports",
) -> None:
    """Upload the workbook + manifest to Supabase Storage.

    The dashboard reads `latest.json` from the same bucket; we PUT the xlsx
    first and the manifest second so the manifest never points at a file
    that hasn't been uploaded yet.
    """
    import json
    import re

    from peerbench.storage import SupabaseStorageClient, build_manifest

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )

    if not file.exists():
        typer.echo(f"workbook not found: {file}", err=True)
        raise typer.Exit(code=2)

    # Parse quarter_id from filename: peerbench_<cert>_<quarter>.xlsx
    match = re.match(r"peerbench_\d+_(\d{4}-Q[1-4])\.xlsx$", file.name)
    if not match:
        typer.echo(
            f"filename {file.name!r} does not match peerbench_<cert>_<quarter>.xlsx",
            err=True,
        )
        raise typer.Exit(code=2)
    quarter_id = match.group(1)

    settings = get_settings()
    public_url_base = f"{settings.supabase_url.rstrip('/')}/storage/v1/object/public/{bucket}"

    client = SupabaseStorageClient(
        url=settings.supabase_url,
        service_role_key=settings.supabase_service_role_key,
    )

    manifest = build_manifest(
        file,
        anchor_cert=anchor,
        quarter_id=quarter_id,
        public_url_base=public_url_base,
    )

    xlsx_ct = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    client.upload(bucket, "latest.xlsx", file.read_bytes(), xlsx_ct)
    client.upload(
        bucket, "latest.json", json.dumps(manifest, indent=2).encode("utf-8"), "application/json"
    )
    typer.echo(f"uploaded {file.name} → {public_url_base}/latest.xlsx")


@app.command("export-field-deps")
def export_field_deps(
    out: Annotated[
        Path,
        typer.Option(
            "--out",
            help="Where to write the snapshot. Defaults to web/lib/ratio-field-deps.generated.json.",
        ),
    ] = Path("web/lib/ratio-field-deps.generated.json"),
) -> None:
    """Regenerate the handler field-dependency snapshot.

    Walks every registered handler's AST, extracts the FFIEC field codes each
    one reads off the FactView, and writes a JSON map keyed by ratio_id. The
    snapshot feeds both the dashboard's per-cell restatement marker and the
    pipeline's restatement-detector partial flip, so both layers share a single
    source of truth derived from the handler bodies.

    The committed JSON is treated as a contract: the matching test in
    ``tests/contract/test_ratio_registry.py`` re-runs extraction and fails if
    the snapshot is stale. Run this command after any handler edit that touches
    field references.
    """
    import json

    from peerbench.ratio_engine.field_deps import extract_field_deps

    deps = extract_field_deps()
    payload = {rid: sorted(fields) for rid, fields in sorted(deps.items())}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n")
    typer.echo(f"wrote {len(payload)} ratios -> {out}")


@app.command("info")
def info() -> None:
    """Show registry + config sanity dump (no DB writes)."""
    settings = get_settings()
    handlers = registered_handlers()
    typer.echo(f"DB url scheme:    {settings.sqlalchemy_url.split('://')[0]}")
    typer.echo(f"FDIC API key set: {bool(settings.fdic_api_key)}")
    typer.echo(f"Registered:       {len(handlers)} ratio handlers")
    typer.echo(
        f"Field codes:      {len(all_field_codes())} "
        f"({len(all_fields())} FDIC API + {len(all_field_codes()) - len(all_fields())} CDR)"
    )


if __name__ == "__main__":
    app()
