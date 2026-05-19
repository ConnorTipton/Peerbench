"""Peerbench CLI.

Commands:
  peerbench seed-ratios     — Upsert data/ratios.csv into the ratio_defs table.
  peerbench ingest          — Fetch FDIC API facts for a bank-quarter.
  peerbench info            — Quick sanity dump of registry + config.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Annotated

import typer
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from peerbench.config import get_settings
from peerbench.db import Fact, Institution, Quarter, RatioDef, get_session
from peerbench.fdic_fields import all_fields
from peerbench.ingest import FdicClient, upsert_fact
from peerbench.quarters import (
    parse_quarter_id,
    quarter_end_date,
    recent_finalized_quarters,
)
from peerbench.ratio_defs_io import load_ratio_defs
from peerbench.ratio_engine import registered_handlers

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
                upsert_fact(session, cert, qid, field_code, value)
                written += 1
            typer.echo(
                f"  {qid}: {sum(1 for v in data.values() if v is not None)} fields with values"
            )
    typer.echo(f"done: {written} fact upserts across {len(qids)} quarter(s)")


@app.command("info")
def info() -> None:
    """Show registry + config sanity dump (no DB writes)."""
    settings = get_settings()
    handlers = registered_handlers()
    typer.echo(f"DB url scheme:    {settings.sqlalchemy_url.split('://')[0]}")
    typer.echo(f"FDIC API key set: {bool(settings.fdic_api_key)}")
    typer.echo(f"Registered:       {len(handlers)} ratio handlers")
    typer.echo(f"Fields fetched:   {len(all_fields())}")


if __name__ == "__main__":
    app()
