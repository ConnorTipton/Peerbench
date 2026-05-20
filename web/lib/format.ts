/*
 * Display formatting only. No formula logic — per CLAUDE.md the dashboard
 * reads `ratios.value` and formats; never computes. `ratios.value` is stored
 * as a fraction (verified against src/peerbench/validate.py:8 and handlers),
 * so all 30 ratios render via a single percent formatter.
 *
 * Negatives in parentheses per docs/design.md §Don'ts — minus signs are forbidden.
 * Note: Intl.NumberFormat's `currencySign: "accounting"` is honored only for
 * `style: "currency"`. For `style: "percent"` we wrap negatives manually.
 */

const PERCENT_FMT = new Intl.NumberFormat("en-US", {
  style: "percent",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

export const EM_DASH = "—";

export function formatRatio(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return EM_DASH;
  }
  if (value < 0) {
    return `(${PERCENT_FMT.format(-value)})`;
  }
  return PERCENT_FMT.format(value);
}

export function formatReportDate(isoDate: string): string {
  // quarters.report_date is a Postgres DATE (UTC midnight); just take the date portion.
  return isoDate.slice(0, 10);
}
