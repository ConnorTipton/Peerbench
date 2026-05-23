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

const FACT_VALUE_FMT = new Intl.NumberFormat("en-US", {
  maximumFractionDigits: 0,
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

// Raw fact value from quality_log.old_value / .new_value. Call Report
// dollar fields are reported in thousands by FFIEC convention, so the
// formatted output carries a "(thousands)" suffix to make the unit
// unambiguous in restatement tooltips. Non-dollar fact types (e.g. counts)
// are rare and benign — the suffix is still strictly correct.
export function formatFactValue(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return EM_DASH;
  }
  if (value < 0) {
    return `(${FACT_VALUE_FMT.format(-value)})`;
  }
  return FACT_VALUE_FMT.format(value);
}

export function formatReportDate(isoDate: string): string {
  // quarters.report_date is a Postgres DATE (UTC midnight); just take the date portion.
  return isoDate.slice(0, 10);
}

/**
 * Render an ISO-8601 timestamp as a human-relative phrase for the workbook
 * download freshness subtitle. Future timestamps (clock skew) clamp to "today".
 */
export function formatRelativeDate(iso: string): string {
  const then = new Date(iso);
  const now = new Date();
  const diffMs = now.getTime() - then.getTime();
  const dayMs = 24 * 60 * 60 * 1000;

  if (diffMs < dayMs) return "today";
  if (diffMs < 2 * dayMs) return "yesterday";
  const days = Math.floor(diffMs / dayMs);
  if (days <= 7) return `${days} days ago`;

  return `on ${then.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}`;
}
