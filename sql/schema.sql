-- Peerbench schema
-- Source of truth: PLAN.md v1.3 → "Schema (Postgres)" section.
-- Target: Supabase Postgres 15.x.
-- Apply order: institutions → quarters → facts → ratio_defs → ratios → quality_log.

CREATE TABLE institutions (
  cert         INT PRIMARY KEY,
  rssd         INT UNIQUE,
  name         TEXT NOT NULL,
  charter      TEXT,
  state        TEXT,
  hq_city      TEXT,
  asset_band   TEXT,
  peer_tier    SMALLINT,
  active       BOOLEAN NOT NULL DEFAULT TRUE,
  acquired_by  INT REFERENCES institutions(cert)
);

CREATE TABLE quarters (
  quarter_id   TEXT PRIMARY KEY,        -- 'YYYY-Qn'
  year         SMALLINT NOT NULL,
  quarter      SMALLINT NOT NULL,
  report_date  DATE NOT NULL,
  ingest_at    TIMESTAMPTZ NOT NULL,
  source       TEXT NOT NULL CHECK (source IN ('fdic_api','ffiec_cdr'))
);

CREATE TABLE facts (
  cert            INT REFERENCES institutions(cert),
  quarter_id      TEXT REFERENCES quarters(quarter_id),
  field_code      TEXT NOT NULL,
  value           NUMERIC,
  restated        BOOLEAN NOT NULL DEFAULT FALSE,
  first_seen_at   TIMESTAMPTZ NOT NULL,
  last_updated_at TIMESTAMPTZ NOT NULL,
  PRIMARY KEY (cert, quarter_id, field_code)
);
CREATE INDEX facts_lookup ON facts (cert, quarter_id);

CREATE TABLE ratio_defs (
  ratio_id              TEXT PRIMARY KEY,
  display_name          TEXT NOT NULL,
  category              TEXT NOT NULL,
  numerator_formula     TEXT NOT NULL,
  denominator_formula   TEXT NOT NULL,
  annualize             BOOLEAN NOT NULL DEFAULT FALSE,
  avg_or_eop            TEXT NOT NULL CHECK (avg_or_eop IN ('AVG','EOP')),
  fdic_precomputed_code TEXT,
  ubpr_concept          TEXT,
  regulatory_threshold  JSONB,
  suppress_when         JSONB,                                                          -- e.g. {"cblr": true} suppresses the ratio for CBLR filers
  notes                 TEXT
);

CREATE TABLE ratios (
  cert            INT,
  quarter_id      TEXT,
  ratio_id        TEXT REFERENCES ratio_defs(ratio_id),
  value           NUMERIC,
  formula_version TEXT NOT NULL,
  data_quality    TEXT NOT NULL CHECK (data_quality IN ('ok','partial','suppressed','mismatch')),
  computed_at     TIMESTAMPTZ NOT NULL,
  PRIMARY KEY (cert, quarter_id, ratio_id)
);
CREATE INDEX ratios_cross_peer ON ratios (ratio_id, quarter_id);

CREATE TABLE quality_log (
  id          BIGSERIAL PRIMARY KEY,
  cert        INT,
  quarter_id  TEXT,
  field_code  TEXT,
  event_type  TEXT NOT NULL CHECK (event_type IN ('missing','suppressed','restated','mismatch')),
  old_value   NUMERIC,
  new_value   NUMERIC,
  detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Row Level Security (Phase 3 — see sql/migrations/0001_enable_rls.sql).
-- The dashboard reads via the Supabase anon key; the pipeline writes via
-- the service-role key (which bypasses RLS). `facts` gets RLS enabled
-- with no policy because the dashboard never reads it directly.
ALTER TABLE institutions ENABLE ROW LEVEL SECURITY;
ALTER TABLE quarters     ENABLE ROW LEVEL SECURITY;
ALTER TABLE ratio_defs   ENABLE ROW LEVEL SECURITY;
ALTER TABLE ratios       ENABLE ROW LEVEL SECURITY;
ALTER TABLE quality_log  ENABLE ROW LEVEL SECURITY;
ALTER TABLE facts        ENABLE ROW LEVEL SECURITY;

CREATE POLICY "dashboard_read" ON institutions FOR SELECT USING (true);
CREATE POLICY "dashboard_read" ON quarters     FOR SELECT USING (true);
CREATE POLICY "dashboard_read" ON ratio_defs   FOR SELECT USING (true);
CREATE POLICY "dashboard_read" ON ratios       FOR SELECT USING (true);
CREATE POLICY "dashboard_read" ON quality_log  FOR SELECT USING (true);

-- Foreign-key covering indexes (Phase 3 — see sql/migrations/0002_add_fk_indexes.sql).
-- Clears the Supabase performance advisor "Unindexed foreign keys" findings.
CREATE INDEX IF NOT EXISTS facts_quarter_id_idx
  ON facts (quarter_id);
CREATE INDEX IF NOT EXISTS institutions_acquired_by_idx
  ON institutions (acquired_by);
