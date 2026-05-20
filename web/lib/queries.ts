import "server-only";

import { createServerSupabase } from "@/lib/supabase";
import {
  cellKey,
  restatementKey,
  type MatrixCell,
  type RatioGroup,
} from "@/lib/matrix-types";
import { CATEGORY_ORDER, RATIO_ORDER } from "@/lib/ratio-order";
import type {
  Institution,
  Quarter,
  QualityLogRow,
  RatioCategory,
  RatioDef,
  RatioValue,
} from "@/types/db";

export type MatrixData = {
  quarter: Quarter;
  institutions: Institution[];
  ratioGroups: RatioGroup[];
  /** Keyed `${cert}|${ratio_id}` */
  cells: Map<string, MatrixCell>;
  /** Set of `${cert}|${quarter_id}` with at least one restatement event. */
  restatedKeys: Set<string>;
};

/**
 * Loads everything needed to render the most-recent-quarter matrix.
 * Anchor cert is intentionally not an argument: this query returns the
 * full peer set; anchor selection is a presentation concern (column
 * tinting, default selector) handled in the page + matrix components.
 */
export async function getMatrixData(): Promise<MatrixData> {
  const supabase = await createServerSupabase();

  // Latest quarter with *computed ratios* — the FDIC API ingest can write a
  // `quarters` row before the compute step populates `ratios` for it
  // (e.g., 2026-Q1 exists with 0 facts before banks file), so anchoring on
  // `quarters.report_date` would point at an empty quarter.
  const latestRatioQuarter = await supabase
    .from("ratios")
    .select("quarter_id")
    .order("quarter_id", { ascending: false })
    .limit(1)
    .single();
  if (latestRatioQuarter.error) throw latestRatioQuarter.error;
  const latestQuarterId = latestRatioQuarter.data.quarter_id;

  const [quarterRes, institutionsRes, defsRes, ratiosRes, restatementsRes] = await Promise.all([
    supabase.from("quarters").select("*").eq("quarter_id", latestQuarterId).single(),
    supabase.from("institutions").select("*").eq("active", true),
    supabase.from("ratio_defs").select("*"),
    supabase.from("ratios").select("*").eq("quarter_id", latestQuarterId),
    // Pull the full restatement row (incl. field_code + old/new values) so
    // Sprint 2's per-cell tooltip lands without a second round-trip.
    supabase
      .from("quality_log")
      .select("cert, quarter_id, field_code, event_type, old_value, new_value, detected_at")
      .eq("quarter_id", latestQuarterId)
      .eq("event_type", "restated"),
  ]);
  if (quarterRes.error) throw quarterRes.error;
  if (institutionsRes.error) throw institutionsRes.error;
  if (defsRes.error) throw defsRes.error;
  if (ratiosRes.error) throw ratiosRes.error;
  if (restatementsRes.error) throw restatementsRes.error;
  const quarter = quarterRes.data as Quarter;

  const institutions = sortInstitutions(institutionsRes.data as Institution[]);
  const ratioGroups = groupRatioDefs(defsRes.data as RatioDef[]);

  const cells = new Map<string, MatrixCell>();
  for (const row of ratiosRes.data as RatioValue[]) {
    cells.set(cellKey(row.cert, row.ratio_id), {
      value: row.value === null ? null : Number(row.value),
      data_quality: row.data_quality,
    });
  }

  const restatedKeys = new Set<string>();
  for (const row of restatementsRes.data as Pick<
    QualityLogRow,
    "cert" | "quarter_id" | "event_type"
  >[]) {
    if (row.cert !== null && row.quarter_id !== null) {
      restatedKeys.add(restatementKey(row.cert, row.quarter_id));
    }
  }

  return { quarter, institutions, ratioGroups, cells, restatedKeys };
}

function sortInstitutions(rows: Institution[]): Institution[] {
  // Anchor (4063) first; remaining peers by name for a stable display.
  return [...rows].sort((a, b) => {
    if (a.cert === 4063) return -1;
    if (b.cert === 4063) return 1;
    return a.name.localeCompare(b.name);
  });
}

function groupRatioDefs(defs: RatioDef[]): RatioGroup[] {
  const ratioRank = new Map(RATIO_ORDER.map((id, i) => [id, i]));
  const byCategory = new Map<RatioCategory, RatioDef[]>();
  for (const def of defs) {
    const bucket = byCategory.get(def.category) ?? [];
    bucket.push(def);
    byCategory.set(def.category, bucket);
  }
  return CATEGORY_ORDER.filter((c) => byCategory.has(c)).map((category) => {
    const inGroup = byCategory.get(category)!;
    inGroup.sort(
      (a, b) =>
        (ratioRank.get(a.ratio_id) ?? Number.MAX_SAFE_INTEGER) -
        (ratioRank.get(b.ratio_id) ?? Number.MAX_SAFE_INTEGER),
    );
    return { category, defs: inGroup };
  });
}
