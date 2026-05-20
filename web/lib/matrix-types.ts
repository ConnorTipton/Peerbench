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

export function cellKey(cert: number, ratioId: string): string {
  return `${cert}|${ratioId}`;
}

// Keyed by `(cert, ratio_id)` so the `r` superscript only renders on cells
// whose underlying inputs actually moved. The field→ratio resolution lives in
// queries.ts (server-side) using the handler-derived snapshot at
// web/lib/ratio-field-deps.generated.json — the dashboard never owns formula
// or dependency logic.
export function restatementKey(cert: number, ratioId: string): string {
  return `${cert}|${ratioId}`;
}
