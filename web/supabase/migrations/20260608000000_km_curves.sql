-- Reconstructed "digitized twin" Kaplan-Meier curves per arm, per endpoint.
-- One row = one treatment arm of one publication for one survival endpoint.
-- Curves are produced offline by the survival-twin pipeline and exist for
-- publications only (keyed by publication_id).
CREATE TABLE km_curves (
  id               TEXT PRIMARY KEY,            -- e.g. publication_Batch-III_3_arm_1
  publication_id   TEXT NOT NULL,               -- e.g. publication_Batch-III_3
  nct_id           TEXT REFERENCES clinical_trials(nct_id),
  cancer_type      TEXT NOT NULL,               -- DB cancer-type string (see getDbCancerType)
  comparison_label TEXT,                         -- groups arms shown together
  arm_name         TEXT NOT NULL,
  endpoint         TEXT NOT NULL,               -- PFS / OS / DFS / ...
  twin_coords      JSONB NOT NULL DEFAULT '[]', -- [{ "time": number, "surv": number }] (surv 0-100)
  published_median NUMERIC,                      -- months
  twin_median      NUMERIC,                      -- reconstructed median (months)
  rate_timepoint   NUMERIC,                      -- months, e.g. 24
  published_rate   NUMERIC,                      -- published % at rate_timepoint
  twin_rate        NUMERIC,                      -- reconstructed % at rate_timepoint
  median_follow_up NUMERIC,                      -- months
  match_pct        NUMERIC,                      -- digitized-twin fidelity %, e.g. 99.4
  n_points         INTEGER,                      -- points used, e.g. 142
  reference        TEXT                          -- publication citation / URL / PMID
);

CREATE INDEX idx_km_curves_cancer_endpoint ON km_curves(cancer_type, endpoint);
CREATE INDEX idx_km_curves_publication      ON km_curves(publication_id);

-- Public read (mirrors trial_outcomes); curves carry no user-private data.
ALTER TABLE km_curves ENABLE ROW LEVEL SECURITY;
CREATE POLICY "km_curves_read" ON km_curves FOR SELECT USING (true);
