-- Phase 3 — enable Row Level Security on all 6 public tables.
--
-- Single BEGIN/COMMIT so anon SELECT never breaks mid-migration:
-- RLS-enabled-without-policy hard-blocks the anon role used by the
-- Next.js dashboard. The 5 dashboard-read tables get permissive
-- `FOR SELECT USING (true)` policies in the same transaction.
--
-- `facts` intentionally gets RLS enabled with NO policy: the dashboard
-- never reads `facts` directly (it reads computed `ratios` only — see
-- web/lib/queries.ts), and the pipeline writes via the service-role
-- key which bypasses RLS. Locking `facts` to service-role-only is the
-- intended posture.
--
-- Rollback (manual; not a migration):
--   ALTER TABLE public.<name> DISABLE ROW LEVEL SECURITY;
-- The policies survive a disable; only DROP POLICY for a permanent
-- rollback. See docs/operations.md.

BEGIN;

ALTER TABLE public.institutions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.quarters     ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ratio_defs   ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ratios       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.quality_log  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.facts        ENABLE ROW LEVEL SECURITY;

CREATE POLICY "dashboard_read" ON public.institutions FOR SELECT USING (true);
CREATE POLICY "dashboard_read" ON public.quarters     FOR SELECT USING (true);
CREATE POLICY "dashboard_read" ON public.ratio_defs   FOR SELECT USING (true);
CREATE POLICY "dashboard_read" ON public.ratios       FOR SELECT USING (true);
CREATE POLICY "dashboard_read" ON public.quality_log  FOR SELECT USING (true);

COMMIT;
