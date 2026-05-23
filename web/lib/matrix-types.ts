import type { RatioCategory, RatioDef, RatioValue } from "@/types/db";

/*
 * Shapes shared between the server-only data layer (lib/queries.ts) and
 * the client matrix component. Pure types + pure key helpers — no server-only
 * imports so this module is safe in both environments.
 */

export type MatrixCell = {
  value: number | null;
  data_quality: RatioValue["data_quality"];
};

export type RatioGroup = {
  category: RatioCategory;
  defs: RatioDef[];
};

// Per-cell restatement detail attached to cells whose underlying field was
// restated this quarter. old_value / new_value are raw field-level values
// from quality_log (thousands of dollars by FFIEC convention for dollar
// fields; raw integers for flag fields like CBLRIND), so they render via
// formatFactValue(), not formatRatio() — the cell shows the computed ratio
// percentage, but the tooltip shows the underlying input that moved.
// `field_code` is the FDIC/CDR identifier (e.g. "LNLSGR") so the tooltip
// can name the field and apply the correct unit suffix.
export type RestatedDetail = {
  field_code: string;
  old_value: number | null;
  new_value: number | null;
  detected_at: string;
};

export function cellKey(cert: number, ratioId: string): string {
  return `${cert}|${ratioId}`;
}

// Drilldown route holds one ratio constant and varies (cert, quarter_id),
// the inverse of the matrix. Kept as a separate helper so the call sites
// document which axis is being held constant — silently sharing `cellKey`'s
// signature would invite the wrong tuple at one of the call sites.
export function timeSeriesPointKey(cert: number, quarterId: string): string {
  return `${cert}|${quarterId}`;
}

// Keyed by `(cert, ratio_id)` so the `r` superscript only renders on cells
// whose underlying inputs actually moved. The field→ratio resolution lives in
// queries.ts (server-side) using the handler-derived snapshot at
// web/lib/ratio-field-deps.generated.json — the dashboard never owns formula
// or dependency logic.
export function restatementKey(cert: number, ratioId: string): string {
  return `${cert}|${ratioId}`;
}
