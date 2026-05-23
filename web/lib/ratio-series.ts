import { timeSeriesPointKey, type MatrixCell } from "@/lib/matrix-types";
import type { Institution, Quarter } from "@/types/db";

/*
 * Pure helpers for the per-ratio drilldown route. Shared between the
 * server-only data layer (`lib/queries.ts`) and the client trend chart, so
 * they live outside both. No Supabase, no React — testable in isolation.
 */

/**
 * Given a stream of `{quarter_id}` rows ordered DESCENDING by quarter_id,
 * return the first `n` distinct quarter_ids in first-seen order. Used by
 * `getRatioTimeSeries` to collapse a per-(cert, ratio_id, quarter_id) result
 * set into a unique most-recent-quarters window without an extra round-trip.
 *
 * The DESCENDING input invariant is honored by the caller's `.order(...,
 * { ascending: false })` clause. Out-of-order input would silently yield
 * the wrong window — assert that ordering contract in the call site, not
 * here, so this stays a pure dedupe.
 */
export function selectRecentQuarterIds(
  rows: ReadonlyArray<{ quarter_id: string }>,
  n: number,
): string[] {
  const out: string[] = [];
  const seen = new Set<string>();
  for (const row of rows) {
    if (out.length >= n) break;
    if (seen.has(row.quarter_id)) continue;
    seen.add(row.quarter_id);
    out.push(row.quarter_id);
  }
  return out;
}

/**
 * One row of trend-chart data: `quarter_id` plus a per-peer column
 * (`cert_<n>`) holding that peer's value for the quarter. `null` when the
 * underlying cell is missing or its value is null — Recharts treats that as
 * a gap (`connectNulls={false}`) rather than a zero crossing.
 */
export type TrendChartRow = {
  quarter_id: string;
} & Record<string, string | number | null>;

/**
 * Shape the `(quarters × institutions × MatrixCell)` cross-section into the
 * row-per-quarter array Recharts expects. Pure — no DOM, no I/O.
 */
export function buildTrendChartData(
  quarters: ReadonlyArray<Quarter>,
  institutions: ReadonlyArray<Institution>,
  values: ReadonlyMap<string, MatrixCell>,
): TrendChartRow[] {
  return quarters.map((q) => {
    const row: TrendChartRow = { quarter_id: q.quarter_id };
    for (const inst of institutions) {
      const cell = values.get(timeSeriesPointKey(inst.cert, q.quarter_id));
      row[`cert_${inst.cert}`] = cell?.value ?? null;
    }
    return row;
  });
}
