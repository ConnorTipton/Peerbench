-- Phase 4 follow-up — server-side DISTINCT for the matrix's "ratios with
-- any non-null value" presence filter (surfaced by PR #23 reviewer).
--
-- Background: `getMatrixData` needs the set of ratio_ids whose handler
-- has ever produced a real value, so it can hide defs whose handler
-- always raises NotImplementedError (e.g. `top_loan_cat` pending RC-C
-- field expansion — the ratio engine writes `partial` rows with
-- `value=null`, so a presence-only check isn't enough). PostgREST can't
-- express DISTINCT, so the previous wire query pulled every non-null
-- row (~1.1k today, ~150/quarter growth) and deduped in JavaScript,
-- guarded by a 50k row safety cap. This view pushes the DISTINCT into
-- Postgres so the wire response is capped at ~30 rows regardless of
-- how many cert/quarter/ratio combinations exist.
--
-- security_invoker = true: the view executes with the caller's
-- permissions, so the anon-role RLS policy on `ratios`
-- (`FOR SELECT USING (true)`) governs which rows the view sees.
-- Without this, the view runs as its owner (postgres) and bypasses
-- RLS — fine for read-only ratio_ids today but a security smell.
-- Requires PG15+, which Supabase Postgres is on.
--
-- Idempotent: CREATE OR REPLACE survives re-runs; explicit GRANTs are
-- repeated to handle a fresh schema.sql clone where the view exists
-- but the per-role privileges are not yet set.

CREATE OR REPLACE VIEW public.v_ratios_with_data
  WITH (security_invoker = true) AS
  SELECT DISTINCT ratio_id
  FROM public.ratios
  WHERE value IS NOT NULL;

GRANT SELECT ON public.v_ratios_with_data TO anon, authenticated;
