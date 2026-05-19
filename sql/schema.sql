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
