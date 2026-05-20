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

export function restatementKey(cert: number, quarterId: string): string {
  return `${cert}|${quarterId}`;
}
