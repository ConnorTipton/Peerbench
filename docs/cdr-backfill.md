# FFIEC CDR historical backfill (Phase 5.1)

The daily cron re-fetches the trailing 8 quarters automatically. Phase 5
adds a `/statements` view with up to 24 quarters of history, so the
older 16 quarters (2020-Q1 through 2023-Q4) need to be ingested **once**
from manually-downloaded ZIPs. After this one-time backfill, no further
manual download is required — the existing 8-quarter rolling window
covers everything that can still restate.

## Why manual?

The FFIEC CDR bulk endpoint is an interactive ASP.NET form. It cannot be
hit with a plain HTTP GET; a real browser session has to submit
`Subject Data Format` for the chosen quarter and save the resulting
~hundreds-of-MB ZIP. Automating this would mean a Selenium/Playwright
scraper, which the project rules forbid (`CLAUDE.md` → Don'ts → "No
scraping"). See [`cdr-ingest.md`](./cdr-ingest.md) for the same
constraint applied to the existing 8-quarter window.

## Procedure (one-time per quarter)

1. Visit <https://cdr.ffiec.gov/CDR/Public/CDRDownload.aspx>.
2. Under **Public Distribution Files**, choose `Bulk Data — Call Reports`.
3. Select **Subject Data Format** and the quarter you want.
4. Submit; wait for the ZIP.
5. Rename and place at `cache/cdr/YYYY-Qn.zip` (the `cache/` directory is gitignored).

Then run the backfill from the repo root:

```bash
uv run peerbench backfill --start 2020-Q1 --end 2023-Q4
```

The command loops `(cert, quarter)` calling `ingest` (FDIC API) and
`ingest-cdr` (FFIEC CDR ZIPs). It is idempotent — re-run after fixing
any missing ZIPs and the upsert + restatement detector pick up only the
diffs.

## 16-quarter checklist

| # | Quarter   | Expected ZIP filename                                  | Downloaded? |
|---|-----------|--------------------------------------------------------|-------------|
| 1 | 2020-Q1   | `cache/cdr/2020-Q1.zip` (FFIEC bulk report 03/31/2020) | [ ]         |
| 2 | 2020-Q2   | `cache/cdr/2020-Q2.zip` (FFIEC bulk report 06/30/2020) | [ ]         |
| 3 | 2020-Q3   | `cache/cdr/2020-Q3.zip` (FFIEC bulk report 09/30/2020) | [ ]         |
| 4 | 2020-Q4   | `cache/cdr/2020-Q4.zip` (FFIEC bulk report 12/31/2020) | [ ]         |
| 5 | 2021-Q1   | `cache/cdr/2021-Q1.zip` (FFIEC bulk report 03/31/2021) | [ ]         |
| 6 | 2021-Q2   | `cache/cdr/2021-Q2.zip` (FFIEC bulk report 06/30/2021) | [ ]         |
| 7 | 2021-Q3   | `cache/cdr/2021-Q3.zip` (FFIEC bulk report 09/30/2021) | [ ]         |
| 8 | 2021-Q4   | `cache/cdr/2021-Q4.zip` (FFIEC bulk report 12/31/2021) | [ ]         |
| 9 | 2022-Q1   | `cache/cdr/2022-Q1.zip` (FFIEC bulk report 03/31/2022) | [ ]         |
| 10 | 2022-Q2  | `cache/cdr/2022-Q2.zip` (FFIEC bulk report 06/30/2022) | [ ]         |
| 11 | 2022-Q3  | `cache/cdr/2022-Q3.zip` (FFIEC bulk report 09/30/2022) | [ ]         |
| 12 | 2022-Q4  | `cache/cdr/2022-Q4.zip` (FFIEC bulk report 12/31/2022) | [ ]         |
| 13 | 2023-Q1  | `cache/cdr/2023-Q1.zip` (FFIEC bulk report 03/31/2023) | [ ]         |
| 14 | 2023-Q2  | `cache/cdr/2023-Q2.zip` (FFIEC bulk report 06/30/2023) | [ ]         |
| 15 | 2023-Q3  | `cache/cdr/2023-Q3.zip` (FFIEC bulk report 09/30/2023) | [ ]         |
| 16 | 2023-Q4  | `cache/cdr/2023-Q4.zip` (FFIEC bulk report 12/31/2023) | [ ]         |

The 2024-Q1 through 2025-Q4 ZIPs should already be in `cache/cdr/` from
the existing 8-quarter rolling window. (Confirm with `ls cache/cdr/`.)

## Known schema drift risks

The Phase 5.1 `cdr_schema._STABLE` mapping was empirically verified
against the 2025-Q4 ZIP. Older quarters may have MDRM differences:

- **CECL adoption (2020-Q1 to 2022-Q4)**: `RIADJJ33` (provision for
  credit losses on financial assets) replaced the pre-CECL `RIAD4230`
  (provision for loan and lease losses). SAB-122 banks adopted CECL on
  2020-Q1; most others by 2023-Q1. If `backfill` reports missing
  `CDR_RI_PROV` for early quarters, add a quarter-specific
  `_OVERRIDES` entry in `cdr_schema.py` pointing at `RIAD4230`.
- **ACL nomenclature**: `RCFD3123` was renamed from "ALLL" to "ACL" but
  the MDRM number is stable. No fix expected.
- **HTM under CECL**: `RCFDJJ34` only exists post-CECL. For pre-2020
  banks, fall back to `RCFD1754` if available.

The `cdr.py` parser raises `ValueError` with a clear "column not in
header" message if a quarter's ZIP doesn't have the expected MDRM. Use
that as the trigger to add `_OVERRIDES`. The `backfill` CLI continues
past CDR failures for a given quarter — FDIC API ingest is unaffected.

## After backfill

```bash
# Confirm fact density across the 24-quarter window
uv run python -c "
from peerbench.db import Fact, get_session
from sqlalchemy import select, func
with get_session() as s:
    rows = s.execute(
        select(Fact.quarter_id, func.count(Fact.value))
        .where(Fact.field_code.startswith('CDR_'))
        .group_by(Fact.quarter_id)
        .order_by(Fact.quarter_id)
    ).all()
    for q, n in rows:
        print(f'{q}: {n} CDR facts')
"

# Recompute ratios across the expanded window so the dashboard picks
# up historical data
for cert in $(uv run peerbench list-peers --tier all); do
  uv run peerbench compute --cert "$cert" --quarters 24
done

# Spot-check
uv run peerbench validate-statements --cert 4063 --quarter 2025-Q4
```

## Why isn't this automated?

Same two options exist as for the rolling 8-quarter window
(see `cdr-ingest.md` → "Why isn't this automated?"): scraping is out of
scope, and the FFIEC machine-to-machine API requires credentials. The
backfill is a one-time event per project; ongoing operations rely on the
existing 8-quarter rolling window which is automated via the daily cron.
