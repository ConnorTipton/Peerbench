/*
 * Postgres row types for the tables the dashboard reads.
 * snake_case columns mirror sql/schema.sql exactly — do not camelCase at the boundary.
 * Replace with `mcp__supabase__generate_typescript_types` output if the schema grows.
 */

export type Institution = {
  cert: number;
  rssd: number | null;
  name: string;
  charter: string | null;
  state: string | null;
  hq_city: string | null;
  asset_band: string | null;
  peer_tier: number | null;
  active: boolean;
  acquired_by: number | null;
};

export type Quarter = {
  quarter_id: string;
  year: number;
  quarter: number;
  report_date: string;
  ingest_at: string;
  source: "fdic_api" | "ffiec_cdr";
};

export type RatioCategory =
  | "profitability"
  | "yields"
  | "balance_sheet"
  | "asset_quality"
  | "capital"
  | "concentration"
  | "liquidity";

export type RatioDef = {
  ratio_id: string;
  display_name: string;
  category: RatioCategory;
  numerator_formula: string;
  denominator_formula: string;
  annualize: boolean;
  avg_or_eop: "AVG" | "EOP";
  fdic_precomputed_code: string | null;
  ubpr_concept: string | null;
  regulatory_threshold: Record<string, unknown> | null;
  suppress_when: Record<string, unknown> | null;
  notes: string | null;
};

export type DataQuality = "ok" | "partial" | "suppressed" | "mismatch";

export type RatioValue = {
  cert: number;
  quarter_id: string;
  ratio_id: string;
  value: number | null;
  formula_version: string;
  data_quality: DataQuality;
  computed_at: string;
};

export type QualityLogEvent = "missing" | "suppressed" | "restated" | "mismatch";

export type QualityLogRow = {
  id: number;
  cert: number | null;
  quarter_id: string | null;
  field_code: string | null;
  event_type: QualityLogEvent;
  old_value: number | null;
  new_value: number | null;
  detected_at: string;
};
