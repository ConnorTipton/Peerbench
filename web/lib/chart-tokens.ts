/*
 * Numeric design-token mirror for Recharts components.
 *
 * Recharts requires JS-side numeric `fontSize` props; it cannot read CSS
 * variables. This module mirrors the `@theme` typography tokens defined in
 * `web/app/globals.css` so chart text uses the same scale as the rest of
 * the dashboard.
 *
 * Convention: when a value here changes, the matching @theme line in
 * `globals.css` MUST change in lockstep. The link is documented in
 * `docs/design.md` §Typography — the canonical token tier is 24/16/14/12/10
 * (page-title / section-header / body / table-data / superscript), and
 * charts pick from that menu rather than inventing new sizes.
 *
 * Established by design-critic during Sprint 2 PR-E: any `fontSize: N`
 * literal in chart code is a token drift, not a one-off. See the PR-D
 * `--text-superscript` precedent for the same rule applied to superscript
 * indicators in the matrix.
 */

export const CHART_FONT_SIZE = {
  /** Tick labels on axes; mirrors `--text-table-data` (12px). */
  tableData: 12,
  /** Axis labels and quarter chrome; mirrors `--text-superscript` (10px). */
  superscript: 10,
} as const;
