import type { RatioCategory } from "@/types/db";

/*
 * Display order for the ratio matrix. Mirrors the row order in
 * data/ratios.csv, which is the analyst-facing presentation order
 * (profitability flows into yields, then balance-sheet mix, etc.).
 *
 * The Postgres schema does not store sort_order; ordering lives in
 * the TS layer until a sort_order column is added (out of scope here).
 */

export const CATEGORY_ORDER: readonly RatioCategory[] = [
  "profitability",
  "yields",
  "balance_sheet",
  "asset_quality",
  "capital",
  "concentration",
  "liquidity",
] as const;

export const CATEGORY_LABELS: Record<RatioCategory, string> = {
  profitability: "Profitability",
  yields: "Yields & costs",
  balance_sheet: "Balance sheet mix",
  asset_quality: "Asset quality",
  capital: "Capital",
  concentration: "Concentration",
  liquidity: "Liquidity & deposit composition",
};

export const RATIO_ORDER: readonly string[] = [
  "nim",
  "roa",
  "roe",
  "eff_ratio",
  "ppnr_assets",
  "yield_ea",
  "cost_funds",
  "nis",
  "loans_deposits",
  "loans_assets",
  "sec_assets",
  "cash_assets",
  "deposits_liab",
  "nonint_inc_rev",
  "nonint_exp_assets",
  "tce_ta",
  "npl_ratio",
  "nco_ratio",
  "acl_loans",
  "acl_npl",
  "tier1_lev",
  "tier1_rbc",
  "total_rbc",
  "cet1",
  "cre_rbc",
  "cd_rbc",
  "top_loan_cat",
  "uninsured_dep",
  "brokered_dep",
  "htm_loss_t1",
] as const;
