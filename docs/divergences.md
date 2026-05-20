# Peerbench — Ratio Divergences and Open Items

Permanent home for the catalog of (a) ratios whose handlers raise
`NotImplementedError` and need future work, and (b) intentional
methodology divergences vs FDIC or UBPR. Lives in `docs/` so it
survives session churn and conversation context resets.

Last updated: 2026-05-19 (Task 25 — CDR ingest infrastructure landed).

## NotImplementedError handlers (1 remaining)

Down from 3 at end-of-Day-4. `cet1` and `htm_loss_t1` had their handler
bodies shipped as part of Task 25 (FFIEC CDR ingest); see
"Resolved in Task 25" below.

### `top_loan_cat` — Top Loan Category Concentration

- **Why deferred:** the handler must walk the full RC-C loan-category
  ladder (C&I, consumer, ag, 1-4 family residential, multifamily,
  construction, CRE, leases, foreign). Day 3 had only 3 of ~10
  subcategories ingested (`LNRECONS`, `LNREMULT`, `LNRENRES`), which a
  prior version of the handler incorrectly classified as `ok` — codex
  review caught it, and we deliberately reverted to `NotImplementedError`
  rather than ship a partial answer.
- **What's needed:** expand `src/peerbench/fdic_fields.py` with the rest
  of RC-C, re-ingest the 5-bank slice, then implement the `MAX(category)
  / total_loans` handler body.
- **Optional defer:** if the Phase 2 dashboard doesn't surface this
  ratio in the v1 cut, the work can slide to Phase 4.

## Methodology divergences (intentional)

### NIM tax-equivalent gap (Peerbench vs UBPR)

We report `nim` on a non-tax-equivalent basis to match FDIC's `NIMY`.
UBPR's NIM is tax-equivalent (munis grossed up to pre-tax). Expected
5–15 bp upward gap in UBPR for banks with material muni portfolios.
Our `nim` matches `NIMY` to fractions of a bp.

See [`docs/ratios/nim.md`](./ratios/nim.md) for the worked example.

### Non-TE yields and cost of funds

Same story as NIM: `yield_ea`, `cost_funds`, and `nis` are all
non-TE. UBPR variants gross up muni / agency yields. Document per peer
in interview conversation but no methodology change planned.

## Resolved in Task 25 (CDR ingest)

### `cet1` — handler shipped, awaiting first live CDR ZIP

- **Status:** handler is now `return f["CDR_CET1_CAPITAL"] / f["RWAJT"]`.
  Will produce `data_quality='ok'` once `CDR_CET1_CAPITAL` facts are
  populated by `peerbench ingest-cdr` (procedure:
  [`docs/cdr-ingest.md`](./cdr-ingest.md)).
- **Source field:** FFIEC CDR Schedule RC-R Part I, MDRM `RCOA8274` (pinned
  in `src/peerbench/ingest/cdr_schema.py`; flagged TODO-verify against a
  real ZIP at first live ingest).
- **Suppressed for CBLR filers** via `ratio_defs.suppress_when = {"cblr": true}`.

### `htm_loss_t1` — handler shipped, awaiting first live CDR ZIP

- **Status:** handler is now
  `return (f["SCHA"] - f["CDR_HTM_FAIRVAL"]) / f["RBCT1J"]`. Same gate
  as `cet1` — needs `CDR_HTM_FAIRVAL` facts populated via
  `peerbench ingest-cdr`.
- **Source field:** FFIEC CDR Schedule RC-B Memorandum 2(d), MDRM `RCFD1773`.
- **Post-SVB heuristic:** amber flag at ≥25% of Tier 1 capital.

## Known tech debt — quarter `source` ambiguity

`quarters.quarter_id` is the sole PK on the `quarters` table, with a
`source IN ('fdic_api','ffiec_cdr')` CHECK constraint. When the FDIC API
ingest creates a row for `2025-Q4` tagged `fdic_api`, the subsequent CDR
ingest for the same quarter cannot insert a second row — the PK collides.
CDR-sourced facts therefore piggyback on the FDIC-API row, and the
`quarters.source` column ends up reflecting only the first source seen.

Workaround (not a bug): downstream consumers should not treat
`quarters.source` as "which source produced this fact." The authoritative
signal is the `field_code` prefix (`CDR_*` ⇒ CDR-sourced). Resolving
this cleanly would require a multi-column PK migration on `quarters`,
which is out of scope for Phase 1.

## Resolved in Day 4

### `npl_ratio` — CSV mapping fix (no formula change)

The original Day 3 validation reported a ~1004 bps gap vs FDIC.
Root cause: `data/ratios.csv` had `npl_ratio.fdic_precomputed_code =
LNRESNCR` (allowance / noncurrent — that's `acl_npl`'s comparison
target, not `npl_ratio`'s). The correct comparison is `NCLNLSR`
(Noncurrent Loans to Loans). Handler `NCLNLS / LNLSGR` was already
correct.

Day 4 fix: swapped `npl_ratio` → `NCLNLSR` and filled the previously
empty `acl_npl.fdic_precomputed_code` with `LNRESNCR`. Validation now
shows both at 0.00 bps. Commit `943b23f`.

### `eff_ratio` — formula update to match FDIC EEFFR

FDIC's `EEFFR` text: "Noninterest expense **less amortization of
intangible assets** as a percent of net interest income plus noninterest
income." Our handler used raw NONIX, producing a steady ~26 bps upward
drift.

Day 4 fix: handler body became
`(NONIX - (EAMINTAN or 0)) / (NIM + NONII)`. The `or Decimal(0)` guards
against missing/None values without forcing a partial. EAMINTAN
(Total Amortization Expense and Goodwill Impairment Losses, YTD $) was
added to `INCOME_FIELDS` and ingested. AST snapshot regenerated.
Validation now shows 0.00 bps. Commit `7da8ff6`.

### `loans_deposits` — gross → net loans (matches LNLSDEPR)

FDIC's `LNLSDEPR` is net loans / deposits (`LNLSGR - LNATRES -
LNCONTRA`); our handler used gross loans, drifting ~100 bps. `LNLSNET`
was already in the ingest list, so this was a one-line handler swap
(`LNLSGR → LNLSNET`). AST snapshot regenerated. Validation now shows
0.00 bps. Commit `4180ac1`.

This divergence was surfaced by the new `peerbench validate` harness —
prior to Day 4 the gap existed but was unmeasured. The CSV note had
flagged it as a "1-2% gap" since Day 1.

## Residual gaps (within DoD bar but worth noting)

| Ratio | Max bp | Likely cause |
| --- | ---: | --- |
| `roe` | 0.51 | FDIC's pre-computed `ROE` may be truncated to fewer decimals than our compute layer keeps; differences manifest at the 4th-5th decimal of the percent. Well within the <5 bps bar. |
| `nim` | 0.01 | Same: ours keeps full `Decimal` precision; FDIC truncates `NIMY` at 14 decimals. |
| `yield_ea` | 0.02 | Same root cause as `nim`. |

None of these are actionable — they reflect FDIC's published precision,
not a Peerbench bug.

## CBLR suppression (regulatory, not a divergence)

Three ratios are pipeline-level suppressed for CBLR filers via the
`ratio_defs.suppress_when = {"cblr": true}` mechanism:

- `tier1_rbc`
- `total_rbc`
- `cet1`

CBLR filers (small banks electing the Community Bank Leverage Ratio
framework) don't report risk-based capital denominators. The dispatcher
checks `CBLRIND` against `suppress_when` before invoking the handler
and writes `data_quality='suppressed'` if it matches.

None of the 5-bank Phase 1 sample triggers CBLR (all are $40B+, well
above the $10B CBLR opt-in threshold). The suppression path is exercised
by the unit tests; it'll see real production use when broader peer tiers
land in Phase 2.

## Validation status

Current snapshot (2026-05-19, 5 banks × 8 quarters, 500 comparisons):

- **Aggregate: mean 0.02 bps, max 0.51 bps — PASS** vs DoD bar of
  <2 bps mean / <5 bps max.
- See [`docs/validation-snapshot.md`](./validation-snapshot.md) for the
  per-ratio breakdown.
- Re-run any time with
  `uv run peerbench validate --certs 4063,4214,110,11063,5510 --quarters 8 --write-snapshot docs/validation-snapshot.md`.
