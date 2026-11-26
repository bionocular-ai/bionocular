-- ASH 2025 heme outcomes as long rows: one row per resolved value, keyed into
-- a field dictionary, plus the arm_outcomes view the agent reads them through.
-- Loaded by the ASH loader in melanoma/scripts/ with the secret key, through
-- replace_ash_abstract() and delete_ash_abstracts_except() below. ASH arms
-- live in trial_outcomes like every other arm; this adds no column to it.
--
-- RLS and grants mirror trial_outcomes as observed on 2026-11-26 (the anon key
-- reads nothing from it; the app reads it as signed-in users): select for
-- authenticated, everything for service_role, nothing for anon. Check them
-- against `select * from pg_policies where tablename = 'trial_outcomes'` and
-- `\dp trial_outcomes` before applying. Grants are explicit because Supabase
-- no longer exposes new public tables to the API roles by default.

-- One row per field, seeded from melanoma/resources/ash/book1_sheet2.csv.
CREATE TABLE outcome_fields (
  key            TEXT PRIMARY KEY,      -- e.g. pfs_rate_36_mo, the key results.json uses
  label          TEXT NOT NULL UNIQUE,  -- e.g. "PFS rate 36 mo"
  family         TEXT NOT NULL,         -- e.g. response_rates, survival_pfs_os
  scope          TEXT NOT NULL,         -- arm / comparison / trial
  value_type     TEXT NOT NULL,         -- percent, months, months_or_nr, count, ...
  allowed_values TEXT[],                -- for enums
  definition     TEXT NOT NULL,         -- what the agent reads to interpret a value
  wide_column    TEXT,                  -- the trial_outcomes column this field also fills
  sort_order     INTEGER NOT NULL       -- order within the family
);

-- One row per resolved value. No unique key: a source can report the same
-- field and context twice (e.g. two bridging regimens), and the loader
-- replaces an abstract's values wholesale, so no upsert key is needed.
CREATE TABLE outcome_values (
  id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  trial_outcome_id TEXT REFERENCES trial_outcomes(id) ON DELETE CASCADE,  -- null = abstract-level
  source_type      TEXT NOT NULL,         -- 'abstract'
  source_id        TEXT NOT NULL,         -- e.g. ASH_2025_5329 (= trial_outcomes.abstract_id)
  source_url       TEXT,                  -- the DOI link, so arm-less abstracts keep it
  nct_id           TEXT REFERENCES clinical_trials(nct_id),
  cancer_type      TEXT[] NOT NULL,
  field_key        TEXT NOT NULL REFERENCES outcome_fields(key),
  context          TEXT NOT NULL DEFAULT '',  -- an extra's context; empty for the main value
  value_text       TEXT NOT NULL,             -- as written: NR, <0.001, 0.86-3.28, dose text
  value_num        NUMERIC,                   -- parsed for numeric types, else null
  qualifier        TEXT CHECK (qualifier IN ('NR', '<', '<=', '>', '>=')),
  n                INTEGER,
  detail           TEXT NOT NULL DEFAULT '',
  derived          BOOLEAN NOT NULL DEFAULT false,
  origin           TEXT NOT NULL CHECK (origin IN ('abstract', 'registry')),
  caveat           TEXT                       -- the resolved sheet's cell note
);

CREATE INDEX outcome_values_cancer_type_idx ON outcome_values USING gin (cancer_type);
CREATE INDEX outcome_values_trial_outcome_id_idx ON outcome_values (trial_outcome_id);
CREATE INDEX outcome_values_source_id_idx ON outcome_values (source_id);
CREATE INDEX outcome_values_nct_id_idx ON outcome_values (nct_id);
CREATE INDEX outcome_values_field_key_idx ON outcome_values (field_key);

ALTER TABLE outcome_fields ENABLE ROW LEVEL SECURITY;
ALTER TABLE outcome_values ENABLE ROW LEVEL SECURITY;
CREATE POLICY "outcome_fields_read" ON outcome_fields FOR SELECT TO authenticated USING (true);
CREATE POLICY "outcome_values_read" ON outcome_values FOR SELECT TO authenticated USING (true);

-- One row per arm of a source that has long values, plus one "All arms" row
-- per source with pooled (arm-less, non-trial) values. `trial` carries the
-- source's trial-scope values on every row, so a response rate never arrives
-- without its criteria. `values` is keyed by family so a reader can select
-- only some families (values->response_rates). security_invoker makes the
-- caller's RLS and grants apply, not the view owner's.
-- ponytail: aggregates per query; materialize past ~1M outcome_values rows
CREATE VIEW arm_outcomes WITH (security_invoker = true) AS
WITH v AS (
  SELECT ov.*, f.label, f.family, f.scope, f.sort_order, f.wide_column
  FROM outcome_values ov
  JOIN outcome_fields f ON f.key = ov.field_key
),
-- Per source: its DOI link and every drug named on its arms or in its
-- abstract-level generic-name values, so an abstract with no arm rows still
-- carries both and the drug filter finds its "All arms" row.
sources AS (
  SELECT source_id,
         string_agg(DISTINCT drug, '; ') AS abstract_drugs,
         max(source_url) AS source_url
  FROM (
    SELECT t.abstract_id AS source_id, t.generic_name AS drug, t.source_url
    FROM trial_outcomes t
    WHERE t.abstract_id IN (SELECT source_id FROM outcome_values)
    UNION ALL
    SELECT source_id,
           CASE WHEN trial_outcome_id IS NULL AND wide_column = 'generic_name' THEN value_text END,
           source_url
    FROM v
  ) named
  GROUP BY source_id
),
trial AS (
  SELECT source_id, jsonb_object_agg(label, jsonb_strip_nulls(jsonb_build_object(
           'value', value_text, 'origin', origin, 'caveat', caveat))) AS trial
  FROM (
    -- A repeated label joins its values; registry origin and caveats are kept
    -- when any of its entries has them.
    SELECT source_id, label,
           string_agg(value_text, '; ' ORDER BY context, id) AS value_text,
           max(nullif(origin, 'abstract')) AS origin,
           string_agg(DISTINCT nullif(caveat, ''), '; ') AS caveat
    FROM v
    WHERE scope = 'trial'
    GROUP BY source_id, label
  ) per_label
  GROUP BY source_id
),
grouped AS (
  SELECT source_id, trial_outcome_id,
         min(source_type) AS source_type,
         min(nct_id) AS nct_id,
         min(cancer_type) AS cancer_type,
         jsonb_object_agg(family, entries) AS "values"
  FROM (
    SELECT source_id, trial_outcome_id, family,
           min(source_type) AS source_type, min(nct_id) AS nct_id,
           min(cancer_type) AS cancer_type,
           jsonb_agg(jsonb_strip_nulls(jsonb_build_object(
             'field', label,
             'value', value_text,
             'context', nullif(context, ''),
             'n', n,
             'detail', nullif(detail, ''),
             'derived', nullif(derived, false),
             'origin', nullif(origin, 'abstract'),
             'caveat', nullif(caveat, '')
           )) ORDER BY sort_order, context, id) AS entries
    FROM v
    WHERE scope <> 'trial'
    GROUP BY source_id, trial_outcome_id, family
  ) per_family
  GROUP BY source_id, trial_outcome_id
)
SELECT t.id, t.id AS trial_outcome_id, t.source_type, t.abstract_id AS source_id,
       coalesce(t.source_url, s.source_url) AS source_url, t.nct_id, t.cancer_type, t.arm_name, t.generic_name,
       t.num_patients, t.line_of_treatment, t.expert_review,
       s.abstract_drugs, tr.trial, g."values"
FROM trial_outcomes t
JOIN sources s ON s.source_id = t.abstract_id
LEFT JOIN trial tr ON tr.source_id = t.abstract_id
LEFT JOIN grouped g ON g.trial_outcome_id = t.id
UNION ALL
SELECT 'abstract_' || g.source_id || '_all', NULL, g.source_type, g.source_id,
       s.source_url, g.nct_id, g.cancer_type, 'All arms (pooled or trial-level)', NULL,
       NULL, NULL, NULL,
       s.abstract_drugs, tr.trial, g."values"
FROM grouped g
LEFT JOIN sources s ON s.source_id = g.source_id
LEFT JOIN trial tr ON tr.source_id = g.source_id
WHERE g.trial_outcome_id IS NULL;

GRANT SELECT ON outcome_fields, outcome_values, arm_outcomes TO authenticated;
GRANT ALL ON outcome_fields, outcome_values, arm_outcomes TO service_role;

-- Replaces one ASH abstract in one transaction: upserts its arms, deletes its
-- arms no longer sent (their values go with them by cascade), then replaces
-- all of its values, so a value cleared upstream cannot survive a reload.
-- The arm upsert writes only the columns the loader sends, never
-- expert_review or expert_reviewed_at, so an expert's verdict on a surviving
-- arm stays, and so do columns the loader does not own (created_at, ...).
-- The column list is read from the payload's keys rather than spelled out,
-- because the loader fills a changing set of wide columns; an unknown key
-- fails the insert instead of being dropped.
CREATE FUNCTION replace_ash_abstract(abstract_id text, arms jsonb, vals jsonb) RETURNS void
LANGUAGE plpgsql
SET search_path = public, pg_temp
AS $$
DECLARE
  cols text;
  sets text;
BEGIN
  IF coalesce(jsonb_array_length(arms), 0) = 0 AND coalesce(jsonb_array_length(vals), 0) = 0 THEN
    RAISE EXCEPTION 'replace_ash_abstract(%): nothing to load', abstract_id;
  END IF;
  -- Scope every write to this one ASH abstract: the abstract id must be an ASH
  -- id, and each arm's id must be the one derived from it, so the upsert can
  -- never land on another source's row (melanoma rows included) and the
  -- deletes below never reach outside ASH.
  IF abstract_id NOT LIKE 'ASH\_2025\_%' THEN
    RAISE EXCEPTION 'replace_ash_abstract(%): not an ASH 2025 abstract id', abstract_id;
  END IF;
  IF EXISTS (SELECT 1 FROM jsonb_array_elements(arms) a
             WHERE a->>'abstract_id' IS DISTINCT FROM replace_ash_abstract.abstract_id
                OR a->>'source_name' IS DISTINCT FROM 'extraction_results_ASH_2025'
                OR a->>'id' IS DISTINCT FROM
                   'abstract_' || replace_ash_abstract.abstract_id || '_' || (a->>'arm_id'))
     OR EXISTS (SELECT 1 FROM jsonb_array_elements(vals) v
                WHERE v->>'source_id' IS DISTINCT FROM replace_ash_abstract.abstract_id) THEN
    RAISE EXCEPTION 'replace_ash_abstract(%): payload holds rows of another abstract', abstract_id;
  END IF;

  IF jsonb_array_length(arms) > 0 THEN
    SELECT string_agg(format('%I', k), ', '),
           string_agg(format('%I = excluded.%I', k, k), ', ') FILTER (WHERE k <> 'id')
      INTO cols, sets
      FROM (SELECT DISTINCT jsonb_object_keys(a) AS k FROM jsonb_array_elements(arms) a) keys
     WHERE k NOT IN ('expert_review', 'expert_reviewed_at');
    EXECUTE format(
      'INSERT INTO trial_outcomes (%s) SELECT %s FROM jsonb_populate_recordset(null::trial_outcomes, $1)
       ON CONFLICT (id) DO UPDATE SET %s',
      cols, cols, sets
    ) USING arms;
  END IF;

  DELETE FROM trial_outcomes t
   WHERE t.abstract_id = replace_ash_abstract.abstract_id
     AND t.id <> ALL (ARRAY(SELECT a->>'id' FROM jsonb_array_elements(arms) a));

  DELETE FROM outcome_values ov WHERE ov.source_id = replace_ash_abstract.abstract_id;
  INSERT INTO outcome_values (trial_outcome_id, source_type, source_id, source_url, nct_id,
                              cancer_type, field_key, context, value_text, value_num, qualifier,
                              n, detail, derived, origin, caveat)
  SELECT trial_outcome_id, source_type, source_id, source_url, nct_id, cancer_type,
         field_key, context, value_text, value_num, qualifier, n, detail,
         derived, origin, caveat
    FROM jsonb_populate_recordset(null::outcome_values, vals);
END;
$$;

-- Deletes the ASH abstracts the loader no longer sends: their arms (values
-- follow by cascade) and their abstract-level values, matched by the ASH
-- abstract id prefix so an abstract left with no arm row is caught too.
-- Returns how many abstracts were removed.
CREATE FUNCTION delete_ash_abstracts_except(keep text[]) RETURNS integer
LANGUAGE plpgsql
SET search_path = public, pg_temp
AS $$
DECLARE
  removed integer;
BEGIN
  WITH gone_arms AS (
    DELETE FROM trial_outcomes
     WHERE source_name = 'extraction_results_ASH_2025' AND abstract_id <> ALL (keep)
    RETURNING abstract_id
  ),
  gone_values AS (
    DELETE FROM outcome_values
     WHERE source_id LIKE 'ASH\_2025\_%' AND source_id <> ALL (keep)
    RETURNING source_id
  )
  SELECT count(*) INTO removed
    FROM (SELECT abstract_id FROM gone_arms UNION SELECT source_id FROM gone_values) gone;
  RETURN removed;
END;
$$;

-- New functions are executable by everyone, including anonymous API callers,
-- by default. Only the loader's secret key may run these.
REVOKE EXECUTE ON FUNCTION replace_ash_abstract(text, jsonb, jsonb) FROM PUBLIC, anon, authenticated;
REVOKE EXECUTE ON FUNCTION delete_ash_abstracts_except(text[]) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION replace_ash_abstract(text, jsonb, jsonb) TO service_role;
GRANT EXECUTE ON FUNCTION delete_ash_abstracts_except(text[]) TO service_role;
