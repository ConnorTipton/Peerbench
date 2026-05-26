"""Peerbench CLI.

Commands:
  peerbench seed-ratios          — Upsert data/ratios.csv into ratio_defs.
  peerbench sync-peers           — Upsert data/peers.toml into institutions.
  peerbench list-peers           — Emit peer cert numbers (for shell loops).
  peerbench seed-statement-lines — Upsert data/statement_lines.csv into statement_lines.
  peerbench ingest               — Fetch FDIC API facts for a bank-quarter.
  peerbench ingest-cdr           — Read FFIEC CDR ZIPs and upsert CDR_* fields.
  peerbench backfill             — Historical ingest over a quarter range.
  peerbench compute              — Compute ratios for a bank-quarter and persist.
  peerbench validate             — Cross-check ratios against FDIC pre-computed.
  peerbench validate-statements  — Spot-check facts against a truth-fixture JSON.
  peerbench info                 — Quick sanity dump of registry + config.
  peerbench export               — Generate the Phase 4.2 Excel comp workbook.
  peerbench upload-workbook      — Upload the workbook + manifest to Supabase Storage.
  peerbench export-field-deps    — Regenerate the handler field-dependency JSON.
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
from peerbench.db import Fact, Institution, Quarter, Ratio, RatioDef, get_session
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


@app.command("sync-peers")
def sync_peers() -> None:
    """Upsert data/peers.toml into the `institutions` table.

    Idempotent — run after editing peers.toml. Inserts new peers, updates
    cert/name/state/peer_tier on existing rows. Does NOT touch the `active`
    flag or fields populated by the FDIC ingest path (rssd, hq_city, etc.).
    """
    from peerbench.peer_config import load_peers

    peers = load_peers()
    with get_session() as session:
        for peer in peers:
            stmt = pg_insert(Institution).values(
                cert=peer.cert,
                name=peer.name,
                state=peer.state,
                peer_tier=peer.peer_tier,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["cert"],
                set_={
                    "name": stmt.excluded.name,
                    "state": stmt.excluded.state,
                    "peer_tier": stmt.excluded.peer_tier,
                },
            )
            session.execute(stmt)
    typer.echo(
        f"sync-peers: upserted {len(peers)} institutions "
        f"({sum(1 for p in peers if p.peer_tier == 1)} tier-1, "
        f"{sum(1 for p in peers if p.peer_tier == 2)} tier-2)"
    )


@app.command("list-peers")
def list_peers(
    tier: Annotated[
        str,
        typer.Option("--tier", help="Which tier to list: 1, 2, or all"),
    ] = "all",
    sep: Annotated[
        str,
        typer.Option("--sep", help="Separator between cert numbers"),
    ] = " ",
) -> None:
    """Emit peer cert numbers from data/peers.toml.

    Consumed by .github/workflows/daily-ingest.yml to feed the ingest loop —
    `for cert in $(uv run peerbench list-peers --tier 1)`.
    Order matches peers.toml line order (anchor first).
    """
    from peerbench.peer_config import all_certs, tier1_certs, tier2_certs

    if tier == "1":
        certs = tier1_certs()
    elif tier == "2":
        certs = tier2_certs()
    elif tier == "all":
        certs = all_certs()
    else:
        typer.echo(f"--tier must be 1, 2, or all (got: {tier!r})", err=True)
        raise typer.Exit(code=2)
    typer.echo(sep.join(str(c) for c in certs))


@app.command("seed-statement-lines")
def seed_statement_lines() -> None:
    """Upsert data/statement_lines.csv into the `statement_lines` table.

    Idempotent — run after editing the CSV. Cross-checks that every
    field_code referenced in the CSV exists in `CDR_FIELDS` (i.e. the
    ingest pipeline will actually populate it) — refuses to seed otherwise.
    """
    import csv

    from peerbench.db import StatementLine
    from peerbench.fdic_fields import CDR_FIELDS

    from peerbench.config import REPO_ROOT

    csv_path = REPO_ROOT / "data" / "statement_lines.csv"
    with csv_path.open() as fh:
        rows: list[dict[str, str]] = [
            {k: (v or "") for k, v in r.items() if k} for r in csv.DictReader(fh)
        ]

    cdr_set = set(CDR_FIELDS)
    bad_codes = sorted(
        {r["field_code"] for r in rows if r["field_code"] and r["field_code"] not in cdr_set}
    )
    if bad_codes:
        typer.echo(
            f"statement_lines.csv references field_codes not in CDR_FIELDS: {bad_codes}.\n"
            "Add them to peerbench.ingest.cdr_schema._STABLE (and they will appear in CDR_FIELDS "
            "via derived export) before seeding.",
            err=True,
        )
        raise typer.Exit(code=2)

    with get_session() as session:
        for row in rows:
            stmt = pg_insert(StatementLine).values(
                line_id=row["line_id"],
                schedule=row["schedule"],
                line_order=int(row["line_order"]),
                label=row["label"],
                indent_depth=int(row.get("indent_depth") or 0),
                is_subtotal=row["is_subtotal"].strip().upper() == "TRUE",
                parent_line_id=row.get("parent_line_id") or None,
                field_code=row.get("field_code") or None,
                notes=row.get("notes") or None,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["line_id"],
                set_={
                    "schedule": stmt.excluded.schedule,
                    "line_order": stmt.excluded.line_order,
                    "label": stmt.excluded.label,
                    "indent_depth": stmt.excluded.indent_depth,
                    "is_subtotal": stmt.excluded.is_subtotal,
                    "parent_line_id": stmt.excluded.parent_line_id,
                    "field_code": stmt.excluded.field_code,
                    "notes": stmt.excluded.notes,
                },
            )
            session.execute(stmt)
    typer.echo(
        f"seed-statement-lines: upserted {len(rows)} rows "
        f"({sum(1 for r in rows if r['schedule'] == 'RI')} RI, "
        f"{sum(1 for r in rows if r['schedule'] == 'RC')} RC)"
    )


@app.command("backfill")
def backfill(
    start: Annotated[str, typer.Option("--start", help="Earliest quarter, e.g. 2020-Q1")],
    end: Annotated[str, typer.Option("--end", help="Latest quarter, e.g. 2023-Q4")],
    certs: Annotated[
        str | None,
        typer.Option(
            "--certs",
            help="Optional comma-separated certs (default: all peers from peers.toml)",
        ),
    ] = None,
    skip_cdr: Annotated[
        bool,
        typer.Option("--skip-cdr", help="Only run FDIC API ingest; skip CDR for this run"),
    ] = False,
) -> None:
    """Historical backfill of FDIC + FFIEC CDR data for a quarter range.

    Loops over the inclusive quarter range and calls `ingest` (FDIC API)
    and `ingest-cdr` (FFIEC CDR ZIPs) for each cert. Idempotent — re-runs
    upsert and the restatement detector picks up any diffs.

    Pre-requisite for CDR ingest: matching `cache/cdr/YYYY-Qn.zip` files
    must be staged per docs/cdr-backfill.md. If a ZIP is missing, the CDR
    step raises with manual-download instructions; FDIC API ingest is
    unaffected.

    Cert list defaults to all peers in data/peers.toml. Specify --certs
    to backfill a subset (e.g. one new peer added mid-cycle).
    """
    from peerbench.peer_config import all_certs

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    cert_list = _parse_cert_list(certs) if certs else list(all_certs())
    qids = _enumerate_quarter_range(start, end)
    typer.echo(
        f"backfill: certs={cert_list} ({len(cert_list)}) "
        f"quarters={start}..{end} ({len(qids)} total) skip_cdr={skip_cdr}"
    )

    fields = list(all_fields())
    with FdicClient() as fdic, get_session() as session:
        for cert in cert_list:
            _ensure_institution(session, cert, fdic)
            on_diff = make_quality_log_callback(session)
            for qid in qids:
                _ensure_quarter(session, qid, source="fdic_api")
                data = fdic.financials(cert, qid, fields)
                for field_code, value in data.items():
                    if value is None and session.get(Fact, (cert, qid, field_code)) is None:
                        continue
                    upsert_fact(session, cert, qid, field_code, value, on_diff=on_diff)
            typer.echo(f"  fdic done: cert={cert} quarters={len(qids)}")

    if skip_cdr:
        typer.echo("backfill complete (CDR skipped)")
        return

    cdr_client = CdrClient()
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
        on_diff = make_quality_log_callback(session)
        for qid in qids:
            _ensure_quarter(session, qid, source="ffiec_cdr")
            for label in known_labels():
                pattern = SCHEDULE_PATTERN[label]
                candidates = cdr_columns(qid, label)
                field_code = _cdr_field_code(label)
                try:
                    rows = cdr_client.iter_schedule_rows(
                        qid,
                        pattern,
                        required_columns=((RSSD_COLUMN,), candidates),
                    )
                    for row in rows:
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
                except CdrZipNotCachedError as e:
                    typer.echo(f"  cdr skipped: {qid} ({e})", err=True)
                    break
            typer.echo(f"  cdr done: {qid}")
    typer.echo(f"backfill complete: {len(cert_list)} certs × {len(qids)} quarters")


def _enumerate_quarter_range(start: str, end: str) -> list[str]:
    """Inclusive [start, end] quarter range; both args 'YYYY-Qn'."""
    sy, sq = parse_quarter_id(start)
    ey, eq = parse_quarter_id(end)
    if (sy, sq) > (ey, eq):
        msg = f"backfill range invalid: start {start!r} > end {end!r}"
        raise ValueError(msg)
    out: list[str] = []
    y, q = sy, sq
    while (y, q) <= (ey, eq):
        out.append(f"{y}-Q{q}")
        if q == 4:
            y, q = y + 1, 1
        else:
            q += 1
    return out


@app.command("validate-statements")
def validate_statements(
    cert: Annotated[int, typer.Option("--cert", help="FDIC cert number to validate")],
    quarter: Annotated[str, typer.Option("--quarter", help="Quarter id, e.g. 2025-Q4")],
    fixture: Annotated[
        str,
        typer.Option(
            "--fixture",
            help="Path to truth-fixture JSON (default: tests/fixtures/<cert>_<quarter>_truth.json)",
        ),
    ] = "",
    tolerance: Annotated[
        int,
        typer.Option(
            "--tolerance",
            help="Allowed delta in thousands of dollars (FFIEC reports in $k)",
        ),
    ] = 1,
) -> None:
    """Compare ingested statement-line facts against a hand-keyed truth fixture.

    The fixture is a JSON file mapping `field_code` to an integer dollar
    amount (in thousands, matching FFIEC convention). PASS = every fixture
    value within --tolerance of the corresponding `facts.value`. Any miss
    by more than --tolerance fails the gate.

    Used in PR 1 as a "did we ingest the right MDRMs?" smoke test before
    wiring the /statements view. Per the Phase 5.1 plan, fixture is
    typically `tests/fixtures/midfirst_2025q4_truth.json` with ~15 spot
    subtotals from the published Call Report.
    """
    import json

    from peerbench.config import REPO_ROOT

    fixture_path = (
        Path(fixture)
        if fixture
        else REPO_ROOT / "tests" / "fixtures" / f"{cert}_{quarter.lower()}_truth.json"
    )
    if not fixture_path.exists():
        typer.echo(f"truth fixture not found: {fixture_path}", err=True)
        raise typer.Exit(code=2)
    from typing import Any

    truth_raw: Any = json.loads(fixture_path.read_text())
    if not isinstance(truth_raw, dict):
        typer.echo("fixture must be a JSON object mapping field_code -> value", err=True)
        raise typer.Exit(code=2)
    # Strip comment-style keys (e.g. "_README", "_NOTE") so fixtures can carry
    # human-readable preambles without polluting the validation grid.
    truth: dict[str, int] = {}
    # truth_raw is Any (json result narrowed only to "is a dict"); explicit
    # coercion below pins the (str, int) shape the validator requires.
    raw_items: list[tuple[Any, Any]] = list(truth_raw.items())  # pyright: ignore[reportUnknownArgumentType]
    for k_raw, v_raw in raw_items:
        k = str(k_raw)
        if k.startswith("_"):
            continue
        truth[k] = int(v_raw)

    passed = 0
    failed: list[tuple[str, int, int]] = []
    missing: list[str] = []
    with get_session() as session:
        for field_code, expected in truth.items():
            fact = session.get(Fact, (cert, quarter, field_code))
            if fact is None or fact.value is None:
                missing.append(field_code)
                continue
            actual = int(fact.value)
            if abs(actual - expected) <= tolerance:
                passed += 1
            else:
                failed.append((field_code, expected, actual))

    typer.echo(f"validate-statements cert={cert} quarter={quarter}")
    typer.echo(f"  {passed}/{len(truth)} within ±${tolerance}k tolerance")
    if missing:
        typer.echo(f"  MISSING in facts: {missing}", err=True)
    if failed:
        typer.echo("  MISMATCHES:", err=True)
        for code, exp, got in failed:
            typer.echo(f"    {code}: expected={exp!r} actual={got!r}", err=True)
    if missing or failed:
        raise typer.Exit(code=1)


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


def _cdr_field_code(label: str) -> str:
    """Translate a `cdr_schema` label to the namespaced code stored in
    `facts.field_code`. Convention: prepend `CDR_` so CDR-sourced facts
    cannot collide with FDIC API codes when grepping the `facts` table."""
    return f"CDR_{label}"


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
                field_code = _cdr_field_code(label)
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
    """Return MAX(ratios.quarter_id). Raises ValueError if no ratios exist.

    Anchors on the ratios table — not the quarters table — to match the
    dashboard's `getMatrixData` resolution. `_ensure_quarter` can create a
    Quarter row before any banks have filed or ratios have computed; picking
    MAX(Quarter) would then publish an empty-quarter workbook that doesn't
    match what users see on the dashboard.

    Correctness relies on quarter_id following the 'YYYY-Qn' format (e.g.
    '2025-Q4'), where lexicographic order coincides with chronological order.
    """
    latest = session.scalar(select(func.max(Ratio.quarter_id)))
    if latest is None:
        raise ValueError(
            "no ratios in DB — run `peerbench compute` after `peerbench ingest`"
        )
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
