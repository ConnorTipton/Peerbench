/*
 * Per-ratio heat-map direction lookup. Presentational only — `direction`
 * does not live in `ratio_defs` because it's a UI concern (how a value
 * relates to "good" or "bad" in the peer-tier context), not a structural
 * fact about the ratio.
 *
 * Convention:
 *   - higher_is_positive: a larger value indicates better performance
 *     (top quartile → green tint). Example: NIM, ROA, ROE, capital ratios.
 *   - higher_is_negative: a larger value indicates worse performance
 *     (top quartile → red tint). Example: efficiency ratio, NPL, NCO,
 *     funding-risk heuristics.
 *   - neutral: no quartile coloring. Either a strategic choice (balance-
 *     sheet mix) or a regulatory-only-flagged ratio (concentration). These
 *     cells may still receive amber/red regulatory tint via the threshold
 *     resolver, but no quartile-based tint.
 *
 * Stays in 1:1 correspondence with RATIO_ORDER from lib/ratio-order.ts —
 * the type signature there is readonly string[], not a generated union, so
 * the relationship is enforced by a unit test rather than the compiler.
 */

export type RatioDirection = "higher_is_positive" | "higher_is_negative" | "neutral";

export const RATIO_DIRECTIONS: Readonly<Record<string, RatioDirection>> = {
  // Profitability — higher is better, except cost-burden / efficiency.
  nim: "higher_is_positive",
  roa: "higher_is_positive",
  roe: "higher_is_positive",
  eff_ratio: "higher_is_negative",
  ppnr_assets: "higher_is_positive",

  // Yields & costs.
  yield_ea: "higher_is_positive",
  cost_funds: "higher_is_negative",
  nis: "higher_is_positive",

  // Balance sheet mix — strategic choices, not "better" or "worse".
  loans_deposits: "neutral",
  loans_assets: "neutral",
  sec_assets: "neutral",
  cash_assets: "neutral",
  deposits_liab: "neutral",
  nonint_inc_rev: "higher_is_positive",
  nonint_exp_assets: "higher_is_negative",
  tce_ta: "higher_is_positive",

  // Asset quality — lower defaults are better; higher reserve coverage is better.
  npl_ratio: "higher_is_negative",
  nco_ratio: "higher_is_negative",
  acl_loans: "neutral",
  acl_npl: "higher_is_positive",

  // Capital — higher is better.
  tier1_lev: "higher_is_positive",
  tier1_rbc: "higher_is_positive",
  total_rbc: "higher_is_positive",
  cet1: "higher_is_positive",

  // Concentration — regulatory-flagged only, no quartile tint.
  cre_rbc: "neutral",
  cd_rbc: "neutral",
  top_loan_cat: "higher_is_negative",

  // Liquidity & deposit composition — funding-risk heuristics, higher = worse.
  uninsured_dep: "higher_is_negative",
  brokered_dep: "higher_is_negative",
  htm_loss_t1: "higher_is_negative",
};

export function directionFor(ratioId: string): RatioDirection {
  return RATIO_DIRECTIONS[ratioId] ?? "neutral";
}
