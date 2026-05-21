-- Phase 3 — covering indexes for the two unindexed foreign keys flagged
-- by `mcp__supabase__get_advisors type=performance`:
--
--   * facts.quarter_id           -> quarters.quarter_id
--   * institutions.acquired_by   -> institutions.cert
--
-- INFO-level findings (not blockers), but the indexes are tiny on the
-- current dataset (~2.5k facts, 5 institutions) and clear the advisor
-- noise so future findings are easier to triage.
--
-- IF NOT EXISTS makes this idempotent — safe to re-run, safe to apply
-- against a fresh schema.sql clone where the indexes are already part
-- of the canonical schema.

CREATE INDEX IF NOT EXISTS facts_quarter_id_idx
  ON public.facts (quarter_id);

CREATE INDEX IF NOT EXISTS institutions_acquired_by_idx
  ON public.institutions (acquired_by);
