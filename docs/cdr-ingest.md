# FFIEC CDR ingest — manual ZIP placement

Two ratios in Peerbench (`cet1`, `htm_loss_t1`) depend on fields the FDIC
BankFind API does not expose:

- **CET1 capital dollar amount** — FFIEC CDR Schedule RC-R Part I, MDRM `RCOA8274`.
- **HTM securities fair value** — FFIEC CDR Schedule RC-B Memorandum 2(d), MDRM `RCFD1773`.

These come from the FFIEC's bulk Call Report download (Subject Data Format
ZIPs). The bulk endpoint is a form-driven ASP.NET app — it requires
interactive selection of quarter + format and cannot be reached with a
plain HTTP GET. Peerbench therefore expects ZIPs to be **staged manually**
in a local cache and reads from disk only.

## Procedure (one-time per quarter)

1. Visit <https://cdr.ffiec.gov/CDR/Public/CDRDownload.aspx>.
2. Under **Public Distribution Files**, choose `Bulk Data — Call Reports`.
3. Select **Subject Data Format** and the quarter you want (e.g. `2025-Q4`).
4. Submit; wait for the ZIP (~hundreds of MB).
5. Rename and place the file at:

   ```
   cache/cdr/<YYYY-Qn>.zip
   ```

   Example: `cache/cdr/2025-Q4.zip`.

The `cache/` directory is gitignored — these files never enter the repo.

## Running the ingest

After ZIPs are staged:

```bash
# 1. Make sure RSSDID is populated (it is, if you've run `ingest` already)
uv run peerbench ingest --cert 4063 --quarters 8

# 2. Pull CDR fields for the 5-bank sample
uv run peerbench ingest-cdr \
  --certs 4063,4214,110,11063,5510 \
  --quarters 8

# 3. Recompute ratios — fills cet1 + htm_loss_t1 from the new facts
for c in 4063 4214 110 11063 5510; do
  uv run peerbench compute --cert "$c" --quarters 8
done

# 4. Validate end-to-end
uv run peerbench validate \
  --certs 4063,4214,110,11063,5510 --quarters 8 \
  --write-snapshot docs/validation-snapshot.md
```

PASS criteria: validation snapshot reports mean <2 bps / max <5 bps across
15 mapped ratios (previously 13 — `cet1` and `htm_loss_t1` join the set
once their FDIC pre-computed counterparts `IDT1CER` and the HTM fair-value
gap can be cross-checked).

## Schema-map verification

The MDRMs above (`RCOA8274`, `RCFD1773`) are pinned in
`src/peerbench/ingest/cdr_schema.py` from the FFIEC MDRM data dictionary.
The domain prefix (`RCOA` vs `RCFD` vs `RCON`) is non-obvious until you
look at a real ZIP header. After the first successful ingest, confirm
the snapshot row count looks sane (5 banks × 8 quarters × 2 fields = 80
new fact rows) and inspect one row by hand — if `cet1` differs from the
FDIC pre-computed ratio `IDT1CER` by more than a couple bps, the MDRM
or the domain prefix is likely wrong; update the `_STABLE` table in
`cdr_schema.py` and re-ingest.

## Why isn't this automated?

Two options exist for going further:

1. **Selenium / Playwright scraper** against the .aspx form. Works but
   is fragile (any FFIEC layout change breaks it) and adds a heavy
   browser dependency. Out of scope for Phase 1.
2. **FFIEC CDR API access** (machine-to-machine). Available to registered
   users at <https://cdr.ffiec.gov/Public/PWS> but requires credentials.
   Worth revisiting in Phase 3 when the daily cron lands; for now the
   8-quarter backfill is a one-time manual step.
