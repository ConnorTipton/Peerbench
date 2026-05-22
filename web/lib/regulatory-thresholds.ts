/*
 * Regulatory threshold resolver + citations for the amber/red flag layer.
 * Reads numeric triggers from RatioDef.regulatory_threshold (sourced from
 * data/ratios.csv → ratio_defs); citations and footnotes live here because
 * they are presentational source references, not ratio metadata.
 *
 * Architectural rule: the dashboard never hardcodes a numeric threshold
 * value — every percent comes from the JSONB. Citation strings ARE hardcoded
 * because they're plain presentation text (no math) and the 1:1 mapping
 * ratio_id → citation has no analog in the pipeline.
 *
 * JSONB shape (from data/ratios.csv regulatory_threshold column):
 *   { "amber_pct": 300, "red_pct": 400, "amber_growth_pct_36mo": 50 }  ← cre_rbc
 *   { "amber_pct": 100 }                          ← cd_rbc (single-tier amber)
 *   { "amber_pct": 50 }                           ← uninsured_dep
 *   { "amber_pct": 10 }                           ← brokered_dep
 *   { "amber_pct": 25 }                           ← htm_loss_t1
 *   { "min_well_capitalized": 5.0 }               ← capital ratios (informational,
 *     not a heat-map trigger — capital floors don't carry concentration-risk
 *     semantics and are intentionally not flagged here)
 *
 * cre_rbc 36-month growth gate (SR 07-1 §III.A) is intentionally deferred to
 * Phase 4 (will ship as pipeline ratio cre_rbc_growth_36mo). Until then,
 * cre_rbc cells trip amber at ≥300% and red at ≥400% on the level alone,
 * with a footnote on the tooltip.
 *
 * Unit convention: ratios.value is stored as a fraction (0.03 = 3%); JSONB
 * thresholds are expressed as percent integers (300 = 300%). We compare in
 * percent space (value * 100 >= threshold_pct).
 */

import type { RatioDef } from "@/types/db";

export const REGULATORY_CITATIONS: Readonly<Record<string, string>> = {
  cre_rbc: "SR 07-1 / OCC Bulletin 2006-46 (reaffirmed FIL-23-2023)",
  cd_rbc: "SR 07-1 / OCC Bulletin 2006-46",
  brokered_dep: "Heuristic (not regulatory)",
  uninsured_dep: "Post-SVB heuristic",
  htm_loss_t1: "Post-SVB heuristic",
};

export const CRE_GROWTH_GATE_FOOTNOTE =
  "Growth gate not yet wired — see SR 07-1 §III.A for the 36-month ≥50% component.";

export type ThresholdLevel = "amber" | "red";

export type ThresholdResult = {
  level: ThresholdLevel;
  threshold_pct: number;
  citation: string;
  footnote?: string;
};

export function resolveThreshold(
  def: RatioDef,
  value: number | null,
): ThresholdResult | null {
  if (value === null || !Number.isFinite(value)) return null;
  const citation = REGULATORY_CITATIONS[def.ratio_id];
  if (!citation) return null;
  const thresh = def.regulatory_threshold;
  if (!thresh || typeof thresh !== "object") return null;

  const amberPct = readNumber(thresh, "amber_pct");
  const redPct = readNumber(thresh, "red_pct");
  const valuePct = value * 100;

  const footnote =
    def.ratio_id === "cre_rbc" ? CRE_GROWTH_GATE_FOOTNOTE : undefined;

  if (redPct !== null && valuePct >= redPct) {
    return { level: "red", threshold_pct: redPct, citation, footnote };
  }
  if (amberPct !== null && valuePct >= amberPct) {
    return { level: "amber", threshold_pct: amberPct, citation, footnote };
  }
  return null;
}

function readNumber(obj: Record<string, unknown>, key: string): number | null {
  const v = obj[key];
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}
