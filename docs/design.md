# Peerbench — Design Spec

**Status:** authoritative for all dashboard work in Phase 2 and Phase 4.
**Source of truth:** this document. Tailwind v4 `@theme` tokens encode it; component code references tokens only.
**Reference points:** S&P Capital IQ, FactSet, Bloomberg Terminal, FDIC BankFind. Banking dashboards favor **information density over whitespace**.

## Principles

1. **Information density over whitespace.** A senior analyst should see more numbers per square inch than on a marketing page, and read them without effort.
2. **Tokens, not values.** No hex codes, no raw font sizes, no ad-hoc spacing in component code. Every visual choice traces back to a `@theme` token.
3. **Print-aware.** Every page must render correctly to letter-size PDF with black-on-white, no backgrounds, sensible page breaks.
4. **Single accent.** One accent color, used sparingly. Reserve color for data meaning (positive/negative, conditional formatting), not chrome.

## Color palette

Encoded as Tailwind v4 `@theme` CSS variables.

| Token              | Value     | Use                                  |
| ------------------ | --------- | ------------------------------------ |
| `--color-primary`  | `#0A1F3D` | Deep navy; headers, primary surfaces |
| `--color-surface`  | `#FFFFFF` | Page background                      |
| `--color-surface-alt` | `#F8FAFC` | Subtle row alternation (zebra)    |
| `--color-border`   | `#E2E8F0` | Borders, dividers, grid lines        |
| `--color-accent`   | `#1E40AF` | Single accent — used sparingly       |
| `--color-positive` | `#15803D` | Muted green; positive deltas         |
| `--color-negative` | `#B91C1C` | Muted red; negative deltas           |
| `--color-amber`    | `#B45309` | Regulatory amber flags (single-tier or first-tier two-tier) |
| `--color-text`     | `#0F172A` | Primary text                         |
| `--color-text-secondary` | `#64748B` | Secondary text                |
| `--color-text-tertiary`  | `#94A3B8` | Tertiary/labels               |

Conditional-formatting tints derive from `--color-positive`, `--color-negative`, and `--color-amber` at low opacity. Opacity tiers:

- **`/10`** — quartile heat-map tints (top quartile green, bottom quartile red). Subtle; doesn't compete with the value.
- **`/15`** — regulatory amber (single-tier or first-tier of a two-tier ratio). More attention-demanding than quartile, less than red.
- **`/20`** — regulatory red (second-tier of `cre_rbc` at ≥400%). Most attention-demanding tier, still a tint not a fill.

Never use full-saturation fills on data cells.

**Derived tokens.** Tokens whose values compose other tokens via `color-mix()` (e.g. `--color-anchor-tint`) live in `:root` rather than `@theme`. Tailwind v4 can't resolve nested `var()` chains at theme-parse time and silently drops the declaration. They are still canonical design-system tokens; the `:root` placement is a build-time accommodation, not an escape hatch for ad-hoc colors.

## Typography

- **Sans-serif:** Inter, with `font-variant-numeric: tabular-nums` enabled **globally** for all numeric content (set in the root `body` styles via `@theme`).
- **Optional mono** for dense table numerics: JetBrains Mono or IBM Plex Mono.

| Token              | Value | Use                          |
| ------------------ | ----- | ---------------------------- |
| `--text-page-title`     | 24px  | Page-level H1           |
| `--text-section-header` | 16px  | Section H2              |
| `--text-body`           | 14px  | Body, controls, labels  |
| `--text-table-data`     | 12px  | Table cells, dense data |
| `--text-superscript`    | 10px  | Inline annotation markers (restatement `r`, regulatory `△` flag, quartile `●` indicator) |

Weights: 600 for headers, 500 for section labels, 400 for body and data cells.

**Recharts text bridge.** Recharts components need numeric `fontSize` props (can't read CSS vars). `web/lib/chart-tokens.ts` mirrors the typography tokens above as JS numbers — Recharts axis ticks use `--text-table-data` (12); axis labels use `--text-superscript` (10). Never inline a `fontSize` literal in chart code; import from `chart-tokens.ts`.

**Eyebrow label.** Section subheadings on drilldown pages (e.g. `/ratio/<id>` Definition / Formula / Notes) use the `.eyebrow-label` class in `web/app/globals.css` (`@layer components`): 12px (`--text-table-data`), uppercase, `tracking-wide`, `--color-text-tertiary`. Reach for `.eyebrow-label` rather than re-typing the four-utility combination — keeps the eyebrow visual consistent across pages.

## Layout rules

- Information density over whitespace — favor tight padding on data tables (4px y / 8px x).
- **Right-align all numerics, always.** Including in KPI cards.
- **Negatives in parentheses:** `(1,234)` not `-1,234`. Apply via `Intl.NumberFormat` with `currencySign: 'accounting'` or equivalent.
- **Sticky table headers** on vertical scroll.
- **Sticky first column** for row labels in the 25-ratio × N-peers matrix.
- **Subtle border between rows** — grid lines aid readability, do not remove them.
- **"As of [date]" timestamp** top-right of every page, in `--color-text-secondary`.
- **No animations** beyond 200ms ease-in-out transitions on hover / focus / sort state.
- Single accent color in non-data UI (links, focus rings, primary buttons). Anything else competes with the data.

## Conditional formatting heat map

Direction-aware cell tinting on data tables.

- **Light tint behind cell**, never a full-color fill.
- **Top quartile:** `--color-positive` at low opacity tint.
- **Bottom quartile:** `--color-negative` at low opacity tint.
- **Middle two quartiles:** no fill.
- **Direction-aware per ratio.** Higher NIM = positive (green). Higher efficiency ratio = negative (red). CRE concentration: amber above 300%, red above 400% (regulatory thresholds, not quartile-based; see `lib/regulatory-thresholds.ts`).
- Quartile cutoffs are computed per ratio across the currently visible peer set, not against a fixed reference.
- **Cell `●` indicator.** Every quartile-tinted cell (top or bottom, but NOT regulatory-flagged) carries a small focusable `●` superscript in `--text-superscript`, colored `--color-positive` (top) or `--color-negative` (bottom). Hover/focus opens a 3-line tooltip: rank (e.g. "Top quartile for NIM"), value vs peer median, and a direction explanation. The `●` is rendered RIGHT of the value, in the same slot as the regulatory `△` and the restatement `r` — `△` and `●` never coexist on the same cell because regulatory tint replaces quartile tint per the layer-precedence rule.

## Anchor highlighting

The anchor column (currently MidFirst, Cert 4063) gets a low-opacity `--color-primary` tint across every cell so the user can locate it without scanning bank names. The anchor tint is the lowest layer in the per-cell background; quartile and regulatory tints layer on top.

The tint is `--color-primary` at **6%** (`color-mix(in srgb, var(--color-primary) 6%, ...)`), deliberately below the `/10` quartile floor so it never competes with conditional-formatting layers. Encoded as the `--color-anchor-tint` / `--color-anchor-tint-alt` derived tokens (one per zebra row tone). The Excel export mirrors the same 6% blend via `src/peerbench/export/style.py`.

- **Cert subtitle as tooltip trigger.** For the anchor column only, the cert subtitle in the column header reads `Anchor · Cert <n>` and is a focusable `<button>` wrapped in a Radix tooltip. Hover/focus reveals the bank name, the anchor designation, and how to switch via the bank selector. Non-anchor columns keep the plain `Cert <n>` text.
- Switching the anchor via the selector re-applies the tint to the new column. The cert subtitle text and tooltip update accordingly with no extra plumbing — both are derived from `anchorCert` at render time.
- **Trend-chart anchor stroke.** On the `/ratio/<id>` 8-quarter trend chart, the anchor bank renders as a 2.5px stroke in `--color-accent`, drawn last so it sits on top of peer-line overlap. Peers render as 1px strokes in `--color-text-tertiary`. Strip-plot points (peer distribution panel): 6px anchor dot in `--color-accent`, 4px peer dots in `--color-text-tertiary`.

## Restatement indicator

Any ratio cell whose underlying `facts.restated = true` for that quarter gets a small marker (icon or footnote-style superscript) in `--color-text-secondary`. Hover reveals the `quality_log` entry: old value, new value, detected timestamp.

## Regulatory threshold flags

Amber-flag any cell crossing a regulatory threshold defined in `ratio_defs.regulatory_threshold`. Hover tooltip cites the source SR letter or FIL. Layer precedence in the cell background is `amber > red > heatmap tint > anchor tint > zebra` — a regulatory trigger replaces the quartile tint entirely.

- Construction & land development / total RBC ≥ 100% → amber. (SR 07-1 / OCC Bulletin 2006-46.)
- CRE / total RBC ≥ 300% → amber; ≥ 400% → red (two-tier). The SR 07-1 §III.A 36-month ≥50% growth gate is deferred to Phase 4 (will ship as pipeline ratio `cre_rbc_growth_36mo`); a footnote on the amber/red tooltip indicates the growth gate is not yet wired.
- Brokered deposits / total deposits ≥ 10% → amber. (Heuristic, not regulatory.)
- Uninsured deposits / total deposits ≥ 50% → amber. (Post-SVB heuristic.)
- HTM unrealized loss / Tier 1 capital ≥ 25% → amber. (Post-SVB heuristic.)

## Print CSS

`@media print` rules:

- Hide navigation chrome (sidebar, header bar, controls).
- Tables fit letter-size: `8.5in × 11in` with 0.5in margins.
- Black text on white. No background colors, no tints.
- Page breaks between major sections.
- Tabular-nums preserved. Right-align preserved.
- Verify on Summary page and one Comp Sheet drilldown as part of the Phase 4 design pass.

## Excel export design parity

The Phase 4 Excel comp workbook (`uv run peerbench export`) must mirror this spec where Excel allows:

- **Color coding:** inputs `--color-accent` (`#1E40AF`), computed values black, hardcoded values `--color-positive` (`#15803D`).
- **Number formats:** currency `$#,##0;($#,##0)`, percentages `0.00%`. Negatives in parentheses.
- **Conditional formatting** on Summary and time-series tabs: light positive tint for top quartile, light negative tint for bottom quartile, direction-aware per ratio.
- **Frozen panes (Summary tab):** top 2 rows + first 2 columns (openpyxl `freeze_panes = "C3"`). Column A is the "Category" header — section-header rows span it; data rows leave it blank. Column B is the ratio name. Pinning both keeps the section context and ratio label visible during horizontal scroll across peer columns. Other tabs use single-column or single-row freezes per tab semantics (see `src/peerbench/export/writer.py`).
- **Right-align all numerics.** Tabular-nums font.

## Don'ts

- No ad-hoc hex codes in component code — only `@theme` tokens.
- No bright/saturated greens or reds. Match `--color-positive` / `--color-negative` exactly.
- No full-color cell fills on data tables; tints only.
- No animations beyond 200ms transitions.
- No emoji in dashboard chrome or commentary.
- No left-aligned numerics. Ever.
- No minus-sign negatives in numeric display. Parentheses only.
