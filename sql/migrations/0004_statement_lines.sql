-- Phase 5.1 — `statement_lines` table for the /statements view.
--
-- Holds the FFIEC Schedule RI (income statement) and RC (balance sheet)
-- line hierarchy that the /statements dashboard renders. Each row is a
-- single line — header rows have `field_code = NULL`, data rows reference
-- a `CDR_*` code that the ingest pipeline writes to `facts.field_code`,
-- subtotals carry `is_subtotal = TRUE` so the renderer can style them
-- (top border, semibold) and use them as collapse anchors.
--
-- Source of truth for content: `data/statement_lines.csv`. Seeded into
-- this table by `peerbench seed-statement-lines`, which truncates and
-- re-inserts (the CSV is small, hand-edited, banker-reviewable). Edits
-- live in the CSV; running seed-statement-lines is idempotent.
--
-- `parent_line_id` lets the renderer build a tree without a separate
-- structure table. `indent_depth` is redundant with parent depth but
-- pre-computed so the renderer doesn't recurse just to compute indent.
--
-- `v_statement_lines_with_data` mirrors `v_ratios_with_data`: returns
-- only the line_ids whose `field_code` has at least one non-null fact
-- across all (cert, quarter) combinations the dashboard can query.
-- Header rows (field_code NULL) are always included so the renderer
-- can still draw section headers above any visible children.

CREATE TABLE IF NOT EXISTS statement_lines (
  line_id         TEXT PRIMARY KEY,
  schedule        TEXT NOT NULL CHECK (schedule IN ('RI', 'RC')),
  line_order      SMALLINT NOT NULL,
  label           TEXT NOT NULL,
  indent_depth    SMALLINT NOT NULL DEFAULT 0,
  is_subtotal     BOOLEAN NOT NULL DEFAULT FALSE,
  parent_line_id  TEXT REFERENCES statement_lines(line_id),
  field_code      TEXT,
  notes           TEXT
);

CREATE INDEX IF NOT EXISTS idx_statement_lines_schedule_order
  ON statement_lines (schedule, line_order);

-- RLS — dashboard reads via anon role; seed-statement-lines writes via
-- service-role key (which bypasses RLS).
ALTER TABLE statement_lines ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "dashboard_read" ON statement_lines;
CREATE POLICY "dashboard_read" ON statement_lines FOR SELECT USING (true);

-- Server-side filter for "lines that actually have any non-null fact in
-- the facts table" — mirror of `v_ratios_with_data` from migration 0003.
-- Header rows (field_code IS NULL) are always returned so the section
-- structure stays intact above whichever data rows happen to exist.
-- security_invoker = true so the anon-role RLS policy on `facts` and
-- `statement_lines` governs visibility, not the view owner.
CREATE OR REPLACE VIEW public.v_statement_lines_with_data
  WITH (security_invoker = true) AS
  SELECT line_id
  FROM public.statement_lines
  WHERE field_code IS NULL
     OR field_code IN (SELECT DISTINCT field_code
                       FROM public.facts
                       WHERE value IS NOT NULL);

GRANT SELECT ON public.v_statement_lines_with_data TO anon, authenticated;
