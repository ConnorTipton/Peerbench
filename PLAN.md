# Peerbench — Project Plan

**Version:** 1.3
**Last updated:** 2026-05-19
**Owner:** Connor
**Status:** In planning → Phase 1 starting before internship

---

## What this is

Peerbench is a bank peer-benchmarking tool built on FFIEC Call Report data, designed to be useful during your Summer 2026 FP&A internship at MidFirst Bank. MidFirst is the anchor; the tool is generically built so any FDIC-insured bank can be the anchor.

Pipeline: FDIC BankFind API + FFIEC CDR bulk files → Python ratio engine → Supabase Postgres → Next.js dashboard on Vercel.

You're optimizing for two things:
1. A defensible, validated set of bank peer ratios you can talk about confidently in interviews and on the desk.
2. A polished, fast, banking-grade web dashboard that loads in under a second and looks like it belongs in a Treasury group.

You are NOT building: an M&A model, a capital plan, an earnings model, a deposit beta model, or anything that requires non-public data.

---

## Hard constraints

- Public data only (FDIC BankFind API, FFIEC CDR public bulk files).
- No scraping. No screen-scraping the regulator websites for HTML.
- MidFirst-anchored but generically built — the UI must let you swap the anchor bank.
- Internship-prep: ship Phase 1 before May 31, 2026. Ship Phase 2-3 before June 14. Polish through start of internship.

---

## Stack

**Pipeline (Python 3.13)**
- `uv` for environment + lock + run (no poetry, no pip-tools, no pyenv)
- `httpx` for FDIC API
- `pydantic` v2 for validation
- `sqlalchemy` 2.x for DB writes
- `openpyxl` for FFIEC CDR bulk files (xlsx schedules), the FDIC `All Financial Reports.xlsx` schema reference, and the Phase 4 Excel comp workbook export
- `ruff format` and `ruff check` (replaces black + isort + flake8)
- `pyright` for type checking
- `pytest` for tests

**Database**
- Supabase Postgres (free tier, Postgres 15.x)
- Note: free projects pause after 7 days of inactivity → the daily ingest cron itself serves as the heartbeat. No separate heartbeat job needed.
- Note: no automated backups on free → weekly `pg_dump` via GH Action to a private GitHub release.

**Web (Next.js 16)**
- Next.js 16.x (App Router default, React 19.2, Turbopack stable, Cache Components stable)
- Tailwind CSS v4 (CSS-first config via `@theme`)
- shadcn/ui (`npx shadcn@latest init`, New York style, OKLCH colors)
- Recharts for charts; **Tremor Raw blocks** (copy-paste from tremor.so into `components/charts/`) for KPI cards and bar lists. **Do not depend on `@tremor/react` npm package long-term** — Tremor was acquired by Vercel in Feb 2025 and the team is shipping copy-paste blocks, not npm releases.
- TanStack Table v8 for the 25-ratio × N-peers matrix
- `@supabase/ssr` for the Supabase client (not the legacy `auth-helpers`)
- Design tokens (palette, typography, layout rules) live in `docs/design.md` and are encoded in Tailwind v4's `@theme` block. See **Design spec** section below.

**Hosting / automation**
- Vercel Hobby (personal, non-commercial — fine for this project)
- GitHub Actions for the daily ingest cron
- Sentry free tier for error tracking (5K errors/month is plenty)

**Observability**
- Sentry on Next.js
- A `quality_log` table in Postgres for data-quality issues and restatement events
- Vercel logs (1-day retention on Hobby)

**AI tooling**
- Claude Code with `claude-for-financial-services` marketplace
- Install: `claude plugin marketplace add anthropics/financial-services`, then `claude plugin install financial-analysis@claude-for-financial-services` (required core), then `claude plugin install model-builder@claude-for-financial-services` (FP&A-relevant) and optionally `equity-research@claude-for-financial-services` (for commentary writing).
- MCP servers: Context7 (Upstash), Supabase MCP (read-only mode for dev), GitHub MCP, Next.js DevTools MCP (`next-devtools-mcp@latest`).
- Adversarial reviewer pattern: primary agent writes, `reviewer` sub-agent reviews every diff before commit.

---

## Data sources

**Primary: FDIC BankFind Suite API** — `api.fdic.gov/banks/docs`
- Endpoints used: `institutions`, `financials`, `summary`, `history`.
- No API key required, but register for one for rate-limit headroom.
- Pre-computed ratios available (NIMY, ROAY, ROEY, EEFFR, etc.) — use these as validation truth, not as primary values.
- Field codes: pull `api.fdic.gov/banks/docs/All Financial Reports.xlsx` and store as `data/fdic_field_reference.csv` in the repo.

**Secondary: FFIEC CDR bulk data** — `cdr.ffiec.gov/public/`
- Quarterly bulk ZIP files (Subject Data Format).
- Source for Schedule RC-C (loan categories) and RC-R (risk-based capital) granular fields that the FDIC API may not fully expose.
- Ingest via `openpyxl` directly from the bulk ZIPs.

### Release schedule and ingest cadence

Call Reports are due 30 days after each quarter end (35 days for banks with foreign offices). New filings trickle in across the 30–60 day window, late filers can land any time after, and FDIC restates prior-quarter reports for up to ~3 years.

**Ingest runs daily.** Rationale:
1. Restatements arrive on no fixed schedule — daily catches them within a day instead of waiting up to 90 days.
2. Late filers (banks missing the 30-day deadline) are picked up automatically.
3. UBPR is regenerated daily for the most recent quarter, so the pre-computed ratios we validate against can move daily during the active filing window.
4. The daily cron is idempotent (upserts on `facts (cert, quarter_id, field_code)`) and doubles as the Supabase inactivity heartbeat — no separate heartbeat job.

Each daily run re-fetches the **last 8 quarters** (covers ~2 years, which captures the bulk of typical restatements). Beyond 2 years, restatements are rare and can be handled by a manual full-refresh if ever needed.

Practical filing windows where you'll see meaningful new traffic:
- Q1 (Mar 31): peak filing late April – early May
- Q2 (Jun 30): peak filing late July – early August
- Q3 (Sep 30): peak filing late October – early November
- Q4 (Dec 31): peak filing late January – early February

Cost: ~1–2 GH Actions minutes per run × 30 days ≈ 30–60 min/month, well under the 2,000 min/mo private-repo cap.

---

## Ratios

28 ratios in four categories. Each ratio has an entry in `ratio_defs` with: ID, formula, source fields, annualize flag, avg-vs-EOP flag, regulatory threshold (if any), and the FDIC pre-computed code (where one exists).

**Profitability (5)**
- NIM — net interest income (annualized) / avg earning assets. Non-tax-equivalent. Compare to UBPR NIM (which is TE) and document the gap.
- ROA — net income (annualized) / avg total assets
- ROE — net income (annualized) / avg total equity
- Efficiency ratio — non-interest expense / (NII + non-interest income)
- Pre-provision net revenue / avg assets

**Yields / costs (3)**
- Yield on earning assets (non-TE)
- Cost of funds
- Net interest spread

**Balance sheet mix (8)**
- Loans / deposits
- Loans / assets
- Securities / assets
- Cash / assets
- Deposits / liabilities
- Non-interest income / revenue
- Non-interest expense / avg assets
- Tangible common equity / tangible assets

**Asset quality (4)**
- NPL ratio (NPL / total loans)
- Net charge-off ratio (annualized)
- ACL / loans (post-CECL nomenclature — not "ALLL")
- ACL / NPL coverage

**Capital (4)**
- Tier 1 leverage
- Tier 1 RBC
- Total RBC
- CET1 (suppressed for CBLR filers, who instead show CBLR)

**Concentration (3)**
- CRE / total RBC (regulatory flag at 300% with 50% 36-month growth) — also shown as CRE / (Tier 1 + ACL) per Fed S&R Nov 2022 convention
- Construction & land development / total RBC (regulatory flag at 100%)
- Top-loan-category concentration

**Liquidity & deposit composition (3) — new in v1.1**
- Uninsured deposits / total deposits
- Brokered deposits / total deposits
- HTM unrealized loss / Tier 1 capital

### Annualization rule
For YTD income-statement-derived ratios: multiply by `4 / quarter_number`. So Q1 = ×4, Q2 = ×2, Q3 = ×4/3, Q4 = ×1. Q4 is not annualized because YTD = full year. Balance-sheet ratios are not annualized. This matches the UBPR convention on its one-quarter income ratios.

### Average vs period-end
Ratios with income/expense in the numerator (NIM, yield, cost of funds, ROA, ROE, NCO, ACL/loans for some interpretations) use 90-day **average balances from Schedule RC-K** as the denominator. Pure balance-sheet ratios use period-end. The `ratio_defs.avg_or_eop` column controls this per-ratio.

### Tax-equivalent (TE) adjustment
Peerbench reports yields and NIM on a **non-TE basis** for simplicity. UBPR uses TE. The validation step documents the expected gap.

---

## Regulatory thresholds surfaced in the dashboard

Source: Interagency Guidance on Concentrations in Commercial Real Estate Lending (SR 07-1 / OCC Bulletin 2006-46), reaffirmed in FIL-23-2023.

- **Construction & land development / total RBC ≥ 100%** → amber flag
- **CRE / total RBC ≥ 300%** AND **portfolio grew ≥ 50% in last 36 months** → amber flag
- **Brokered deposits / total deposits ≥ 10%** → amber flag (heuristic, not regulatory)
- **Uninsured deposits / total deposits ≥ 50%** → amber flag (post-SVB heuristic)
- **HTM unrealized loss / Tier 1 capital ≥ 25%** → amber flag (post-SVB heuristic)

Hover tooltips cite the source SR letter or FIL.

---

## Peer groups

MidFirst Bank (FDIC Cert #4063, RSSD as listed) is the anchor:
- Total assets ~$41.2B (9/30/2025)
- Privately held by Midland Financial Co. (Johnston family)
- HQ Oklahoma City; footprint OK, AZ, CO, CA, TX
- Heavy CRE and mortgage servicing

**Peer tiers** (verify each Cert # is currently active before locking):
- **Tier 1** — direct comparables: privately held / family-owned large regionals with similar asset size and CRE concentration. [Verify each from your existing list against FDIC BankFind `ACTIVE = 1`.]
- **Tier 2** — public regional banks $20–60B with overlapping business mix.
- **Tier 3** — broader $10–100B regional cohort for distribution context.

Build-time check: if any peer's `ACTIVE` flag flips to 0 between runs, fail the ingest and surface the merger/acquisition in the changelog. This is now caught within a day of the FDIC update, given the daily cron.

---

## Schema (Postgres)

```sql
CREATE TABLE institutions (
  cert         INT PRIMARY KEY,
  rssd         INT UNIQUE,
  name         TEXT NOT NULL,
  charter      TEXT,
  state        TEXT,
  hq_city      TEXT,
  asset_band   TEXT,
  peer_tier    SMALLINT,
  active       BOOLEAN NOT NULL DEFAULT TRUE,
  acquired_by  INT REFERENCES institutions(cert)
);

CREATE TABLE quarters (
  quarter_id   TEXT PRIMARY KEY,        -- 'YYYY-Qn'
  year         SMALLINT NOT NULL,
  quarter      SMALLINT NOT NULL,
  report_date  DATE NOT NULL,
  ingest_at    TIMESTAMPTZ NOT NULL,
  source       TEXT NOT NULL CHECK (source IN ('fdic_api','ffiec_cdr'))
);

CREATE TABLE facts (
  cert            INT REFERENCES institutions(cert),
  quarter_id      TEXT REFERENCES quarters(quarter_id),
  field_code      TEXT NOT NULL,
  value           NUMERIC,
  restated        BOOLEAN NOT NULL DEFAULT FALSE,
  first_seen_at   TIMESTAMPTZ NOT NULL,
  last_updated_at TIMESTAMPTZ NOT NULL,
  PRIMARY KEY (cert, quarter_id, field_code)
);
CREATE INDEX facts_lookup ON facts (cert, quarter_id);

CREATE TABLE ratio_defs (
  ratio_id              TEXT PRIMARY KEY,
  display_name          TEXT NOT NULL,
  category              TEXT NOT NULL,
  numerator_formula     TEXT NOT NULL,
  denominator_formula   TEXT NOT NULL,
  annualize             BOOLEAN NOT NULL DEFAULT FALSE,
  avg_or_eop            TEXT NOT NULL CHECK (avg_or_eop IN ('AVG','EOP')),
  fdic_precomputed_code TEXT,
  ubpr_concept          TEXT,
  regulatory_threshold  JSONB,
  notes                 TEXT
);

CREATE TABLE ratios (
  cert            INT,
  quarter_id      TEXT,
  ratio_id        TEXT REFERENCES ratio_defs(ratio_id),
  value           NUMERIC,
  formula_version TEXT NOT NULL,
  data_quality    TEXT NOT NULL CHECK (data_quality IN ('ok','partial','suppressed','mismatch')),
  computed_at     TIMESTAMPTZ NOT NULL,
  PRIMARY KEY (cert, quarter_id, ratio_id)
);
CREATE INDEX ratios_cross_peer ON ratios (ratio_id, quarter_id);

CREATE TABLE quality_log (
  id          BIGSERIAL PRIMARY KEY,
  cert        INT,
  quarter_id  TEXT,
  field_code  TEXT,
  event_type  TEXT NOT NULL CHECK (event_type IN ('missing','suppressed','restated','mismatch')),
  old_value   NUMERIC,
  new_value   NUMERIC,
  detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

## Design spec (`docs/design.md`)

The dashboard is functional with shadcn/ui + Tailwind v4 + Tremor Raw, but functional isn't the bar. The bar is "looks like it belongs in a Treasury group." This section is the design contract. Implement it as `docs/design.md` and encode the tokens in Tailwind v4's `@theme` block. Reference points: S&P Capital IQ, FactSet, Bloomberg Terminal, FDIC BankFind. Banking dashboards favor **information density over whitespace**.

### Color palette

Encoded as Tailwind v4 `@theme` CSS variables:

- **Primary** `#0A1F3D` (deep navy) — headers, primary surfaces
- **Surface** `#FFFFFF` background, `#F8FAFC` subtle row alternation
- **Borders / dividers** `#E2E8F0`
- **Accent** `#1E40AF` (deep blue) — single accent color, used sparingly
- **Positive** `#15803D` (muted green, not bright)
- **Negative** `#B91C1C` (muted red, not Robinhood-bright)
- **Text** `#0F172A` primary, `#64748B` secondary, `#94A3B8` tertiary

### Typography

- **Sans-serif:** Inter, with `font-variant-numeric: tabular-nums` enabled globally for all numeric content.
- **Optional mono** for table numerics: JetBrains Mono or IBM Plex Mono.
- **Sizes:** 14px body, 12px table data, 24px page titles, 16px section headers.

### Layout rules

- Information density over whitespace.
- Right-align all numerics, always.
- Negatives in parentheses: `(1,234)` not `-1,234`.
- Sticky table headers on scroll; sticky first column for row labels.
- Subtle border between rows — grid lines help readability.
- "As of [date]" timestamp top-right of every page.
- No animations beyond subtle 200ms transitions.

### Conditional formatting heat map

- Light tint behind cell, not full-color fill.
- Top quartile: light green tint.
- Bottom quartile: light red tint.
- Middle: no fill.
- Direction-aware: higher NIM = green, higher efficiency ratio = red, CRE concentration: yellow above 300%, red above 400%.

### Print CSS

`@media print` rules: hide navigation chrome, ensure tables fit letter-size, black text on white, no background colors, page breaks between major sections.

---

## Phases

### Phase 1 — Data pipeline (4 days)

**Definition of done:** all 28 ratios computed for MidFirst and at least 4 peers for the most recent quarter; mean abs error vs FDIC pre-computed < 2 bps; max error < 5 bps; documented divergence for any larger gap; one worked example in `docs/ratios/nim.md`.

- **Day 1** — API + bulk-file inventory. Map every ratio to FDIC API + RC-C/RC-R fallback fields. Output: `ratios.csv` + populated `ratio_defs` table.
- **Day 2** — Pipeline scaffold (uv project, httpx client, Pydantic models, SQLAlchemy schema, Supabase target). Ingest one quarter for MidFirst end-to-end.
- **Day 3** — Ratio engine. Compute all 28 ratios for MidFirst + 4 peers. Wire `quality_log`. Build the restatement detector (see below).
- **Day 4** — Validation. Diff against FDIC pre-computed and one hand-pulled UBPR. Document divergence per-ratio. Ship Phase 1.

**Don't start Phase 2 until Phase 1 ships.**

#### Restatement detector (built in Phase 1, runs every daily ingest)

On each fact upsert:
1. If `(cert, quarter_id, field_code)` exists and incoming `value` ≠ stored `value` (with a small numeric tolerance for floating-point noise), set `facts.restated = true` and update `last_updated_at`.
2. Insert a row into `quality_log` with `event_type = 'restated'`, old and new values.
3. Mark all `ratios` rows for `(cert, quarter_id)` as stale and recompute.

This is what justifies running daily: without the detector, restatements get silently overwritten and you lose the audit trail.

### Phase 2 — Web dashboard (3 days)

**Definition of done:**
- Dashboard loads in <1s on Vercel.
- All 28 ratios render for MidFirst and all peers.
- Ratio matrix supports sort/filter.
- Per-ratio drilldown shows 8-quarter trend.
- Regulatory thresholds surface as amber flags with SR/FIL citations.
- **All pages conform to the design spec in `docs/design.md`.**

All UI conforms to the banking design spec in `docs/design.md` (summarized above in **Design spec**): Tailwind v4 `@theme` tokens for palette and typography, tabular-nums on all numeric content, right-aligned numerics with negatives in parentheses, sticky table headers and first column, and a single accent color. No ad-hoc colors or font sizes in component code — every design choice traces back to a token in `@theme`.

- Anchor selector (defaults to MidFirst Cert 4063)
- Peer-tier toggle
- Ratio matrix (TanStack Table v8, sticky header, tabular-nums, zebra optional)
- Per-ratio drilldown page with 8-quarter trend chart (Recharts) and peer distribution box plot
- Reg-flag panel
- shadcn/ui + Tailwind v4 + Tremor Raw KPI cards (vendored, not npm)
- Restatement indicator on any ratio cell whose underlying `facts.restated = true` for that quarter

### Phase 3 — Hosting & automation (1.5 days)

**Definition of done:** production deploy live; daily ingest cron green for 3 consecutive days; weekly backup cron green; Sentry receiving events.

- Vercel deploy from main
- **GitHub Action: daily ingest cron** (single schedule, ~03:00 UTC). Idempotent upserts; restatement detection built in; doubles as the Supabase inactivity heartbeat. Re-fetches the last 8 quarters each run.
- GitHub Action: weekly `pg_dump` to a private GitHub release (Sunday 04:00 UTC; retain last 8 weekly dumps).
- Sentry wired into Next.js
- Secrets: Vercel env vars (frontend), GH Actions secrets (pipeline)

### Phase 4 — Polish, insights, Excel export, design pass (2.5 days)

**Definition of done:**
- Insight panel surfaces 3 commentary bullets per peer/quarter pair, citing specific schedules.
- **Excel export CLI generates a multi-tab `.xlsx` workbook matching the dashboard's data for the latest quarter, validated against the dashboard view.**
- **Banking design pass complete: tabular-nums everywhere, conditional formatting on all tables, print CSS verified on Summary and Comp Sheet pages.**
- README has install/run/architecture sections.
- One Loom walkthrough recorded; screenshots in `docs/screenshots/` for interview use.

#### Insights
- `/insight` slash command + skill in `.claude/` generates the commentary
- Insight panel in the per-ratio drilldown

#### Excel comp workbook export

**Rationale.** Bankers email spreadsheets, not URLs. Excel is the FP&A vernacular at MidFirst — a senior analyst can mark up an `.xlsx` in track changes; they can't mark up a dashboard. It's also a hosting-failure hedge: if Vercel or Supabase has an outage during the internship, the export still runs as a CLI command against a local Python environment.

**Implementation.**
- CLI: `uv run peerbench export --quarter YYYY-Qn --output ./output/`
- Reads from the same Supabase `ratios` table the dashboard uses — single source of truth, no duplicate computation.
- Uses `openpyxl` (already in the stack).
- Output: one `.xlsx` per run, named `peerbench_<anchor_cert>_<quarter_id>.xlsx`.

**Workbook tabs.**
1. **Cover** — anchor bank, quarter, generation timestamp, data vintage, methodology link.
2. **Summary** — all 28 ratios for anchor + all Tier 1 peers, latest quarter. Anchor row pinned and highlighted. Peer median + anchor rank columns. Conditional formatting for top/bottom quartile.
3. **Comp sheets** — one tab per Tier 1 peer (anchor vs that peer), with three sections:
   - Side-by-side income statement, latest 4 quarters
   - Side-by-side balance sheet, period-end latest quarter
   - Ratios block: formula text + numerator + denominator + values + delta + plain-English meaning column
4. **Time series by category** — one tab per ratio category (profitability, yields/costs, balance sheet mix, asset quality, capital, concentration, liquidity & deposit composition), 8 quarters across all peers.
5. **Restatement log** — pulled from the `quality_log` table; all restated facts that affect ratios shown in the workbook.
6. **Methodology** — every formula, FDIC field code mapping, average-vs-EOP notes, annualization rule, TE/non-TE note, regulatory threshold sources (SR 07-1, OCC Bulletin 2006-46, FIL-23-2023).

**Formatting requirements.**
- **Color coding:** inputs blue (`#1E40AF`), computed values black, hardcoded values green.
- **Number formats:** currency `$#,##0;($#,##0)`, percentages `0.00%`, basis points where appropriate. Negatives in parentheses, not minus signs.
- **Conditional formatting** on Summary and time-series tabs: light green tint for top quartile, light red tint for bottom quartile, direction-aware (higher NIM = green, higher efficiency ratio = red, higher CRE concentration = caution).
- **Frozen panes:** top 2 rows + first column on Summary.
- Right-align all numerics, tabular-nums font.

#### Banking design pass

Apply the **Design spec** section / `docs/design.md` tokens to every page. Verify `font-variant-numeric: tabular-nums` is global. Verify conditional-formatting tints on all data tables follow the heat-map rule. Verify the print CSS by printing the Summary page and one Comp Sheet drilldown to PDF — tables must fit letter-size, no background colors, page breaks between major sections.

#### Polish
- README, ARCHITECTURE.md, screenshots, Loom.

---

## Operational notes

- **Supabase free tier auto-pause**: free projects pause after 7 days of inactivity. The daily ingest cron itself prevents this — no separate heartbeat needed.
- **Supabase backups**: free tier has no automated backups. Weekly `pg_dump` to private GitHub release (retain last 8).
- **Vercel Hobby**: personal/non-commercial only. Don't deploy this on Vercel for MidFirst itself; for a personal portfolio version, fine.
- **FDIC API rate limits**: no hard documented limit, but register a key for headroom. Throttle to 5 req/sec in the pipeline.
- **Restatements**: FDIC restates prior-quarter Call Reports up to ~3 years out. Daily ingest re-fetches the last 8 quarters and runs the restatement detector each cycle. Restated values flip `facts.restated = true`, log to `quality_log`, and trigger ratio recomputation.
- **CBLR filers**: small banks electing the Community Bank Leverage Ratio framework don't report Tier 1 RBC / Total RBC / CET1. Surface CBLR instead and gray out the four risk-based capital ratios with a tooltip.

---

## Changelog

### v1.3 — 2026-05-19

- **Phase 4 expanded to include the Excel comp workbook export.** CLI command `uv run peerbench export --quarter YYYY-Qn --output ./output/`. Six-tab structure (Cover, Summary, Comp Sheets, Time Series by category, Restatement Log, Methodology). Color coding, number formats, conditional formatting, frozen panes, tabular-nums all specified. Reads from the same `ratios` table the dashboard uses — single source of truth, no duplicate computation. Doubles as a hosting-failure hedge.
- **Added Design spec section + `docs/design.md` companion** specced with banking-grade design tokens (palette, typography, layout rules, conditional formatting heat map, print CSS) encoded as Tailwind v4 `@theme` variables. Reference points: S&P Capital IQ, FactSet, Bloomberg Terminal, FDIC BankFind.
- **Phase 2 definition of done expanded** with: "All pages conform to the design spec in `docs/design.md`." Added a paragraph at the top of Phase 2 pointing to the spec and forbidding ad-hoc colors/sizes in component code.
- **Phase 4 definition of done expanded** with Excel export validation and the design pass (tabular-nums everywhere, conditional formatting on all tables, print CSS verified).
- **Phase 4 duration bumped 1.5 → 2.5 days** to reflect the Excel export and design pass scope. No other phase durations changed.
- **Stack section: `openpyxl` note expanded** to call out its Phase 4 role for the comp workbook export. Web subsection: added a line pointing to `docs/design.md` for design tokens.

### v1.2 — 2026-05-19

- **Ingest cadence: quarterly → daily.** Drivers: (1) FDIC restatements arrive on no fixed schedule and were waiting up to a full quarter to be caught; (2) late filers (post-day-35) were being missed under the "Monday after 35 days" window; (3) the daily cron doubles as the Supabase inactivity heartbeat, eliminating the separate weekly heartbeat job. Cost is negligible (~30–60 GH Actions min/month, well under the 2,000 min/mo cap).
- **Added explicit restatement detector** as a built-in step of the daily ingest pipeline: compares incoming values against stored, flips `facts.restated = true`, logs to `quality_log` with old/new values, recomputes affected ratios.
- **Expanded re-ingest window** from last 4 quarters to **last 8 quarters** (covers ~2 years of typical restatement activity). Deep restatements (>2 years out) handled by manual full-refresh if needed.
- **Removed weekly heartbeat GH Action** — daily ingest serves this purpose.
- **Schema additions to `facts`**: `first_seen_at` and `last_updated_at` timestamps to support restatement audit trail.
- **`quality_log` schema upgrade**: added `event_type` enum (`missing | suppressed | restated | mismatch`) and `old_value` / `new_value` columns to capture restatement diffs.
- **Phase 1 Day 3 expanded** to include building the restatement detector.
- **Phase 2 added** restatement indicator on ratio cells with restated underlying facts.

### v1.1 — 2026-05-15

- **Switched primary component library** from `@tremor/react` (npm) to shadcn/ui + Recharts, with Tremor Raw blocks vendored into the repo. Driver: Vercel acquired Tremor in Feb 2025; the npm package has slowed while the team ships copy-paste blocks.
- **Bumped Next.js 15 → 16** (16.2.6 current; React 19.2; stable Turbopack; stable Cache Components; `params` as Promise).
- **Bumped Python 3.12 → 3.13.** Switched from poetry to **uv**; switched from ruff+black+isort to **`ruff format`**; switched from mypy to **pyright**. Removed the `fdicapi` PyPI wrapper in favor of direct `httpx` calls.
- **Added FFIEC CDR bulk file ingestion** as a secondary data source for Schedule RC-C and RC-R granularity.
- **Corrected annualization wording**: factor `4 / quarter_number` is right for Q1-Q3 YTD income, Q4 is not annualized; only applies to income-statement-derived ratios.
- **Specified average-vs-EOP per ratio**: NIM, yield on earning assets, cost of funds, ROA, ROE, NCO use 90-day RC-K averages; balance-sheet ratios use period-end. Added `avg_or_eop` column to `ratio_defs`.
- **Renamed ALLL → ACL** to match post-CECL Call Report nomenclature.
- **Added 3 SVB-era ratios**: uninsured deposits / total deposits, brokered deposits / total deposits, HTM unrealized loss / Tier 1 capital. Total ratios: 25 → 28.
- **Documented both CRE concentration denominators**: total RBC (SR 07-1) and Tier 1 + ACL (Fed S&R Nov 2022).
- **Added CBLR handling**: gray out Tier 1 RBC / Total RBC / CET1 for CBLR filers.
- **Verified Anthropic financial-services marketplace install syntax**: `claude plugin marketplace add anthropics/financial-services` then `claude plugin install <plugin>@claude-for-financial-services`. Right-sized plugin list to: `financial-analysis` (core), `model-builder` (FP&A), `equity-research` (commentary).
- **Added MCP server list**: Context7, Supabase MCP, GitHub MCP, Next.js DevTools MCP.
- **Added explicit CLAUDE.md content**, sub-agent definitions (`reviewer`, `pipeline-validator`, `design-critic`), and slash commands (`/ratio`, `/peer-diff`, `/validate-pipeline`, `/insight`, `/review`).
- **Added full schema**, definition-of-done per phase, day-by-day Phase 1 plan, secrets management approach, and disaster recovery via weekly `pg_dump` to private GitHub release.
- **Added Supabase 7-day inactivity heartbeat** GH Action requirement.
- **Reconfirmed CRE thresholds** (100% construction, 300% CRE with 50% 36-month growth) per SR 07-1 / OCC Bulletin 2006-46.
- **Confirmed MidFirst Bank profile**: ~$41.2B total assets (9/30/2025), privately held by Midland Financial Co., FDIC Cert 4063.

### v1.0 — original

[Original plan as drafted.]
