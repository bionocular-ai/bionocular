-- NCCN-listed therapies and their US regulatory status, per cancer type.
-- One row = one regimen for one cancer type. Loaded from the approved-therapies
-- spreadsheet by melanoma/scripts/upload_approved_therapies.py through
-- replace_approved_therapies() below, which replaces every row in one
-- transaction, so the table holds exactly one NCCN version.
CREATE TABLE approved_therapies (
  cancer_type    TEXT    NOT NULL,  -- DB cancer-type string (see getDbCancerType)
  sheet_row      INTEGER NOT NULL,  -- source sheet row number: NCCN's order, for deterministic
                                    -- ordering only; not a stable regimen ID (shifts if the sheet is reordered)
  treatment_name TEXT    NOT NULL,  -- regimen, e.g. "Ipilimumab + Nivolumab"
  biomarker      TEXT,              -- e.g. "BRAF V600+"; null = no selection
  setting        TEXT    NOT NULL,  -- Neoadjuvant / Adjuvant / 1L+ Advanced / 2L+ / ...
  nccn_tier      TEXT,              -- Preferred / Other Recommended / Useful in certain circumstances
  nccn_category  TEXT,              -- Cat 1 / Cat 2A / Cat 2B
  dose           TEXT,
  us_status      TEXT    NOT NULL,  -- verbatim: Approved / On-label (generic) / Off label / ...
  source         TEXT    NOT NULL,  -- e.g. "NCCN v3.2026"
  PRIMARY KEY (cancer_type, sheet_row)
);

-- Public read (mirrors km_curves); reference data, nothing user-private.
ALTER TABLE approved_therapies ENABLE ROW LEVEL SECURITY;
CREATE POLICY "approved_therapies_read" ON approved_therapies FOR SELECT USING (true);

-- The loader's only write path: one transaction, so a failed insert rolls the
-- delete back and the previous version stays in place. An empty payload is
-- refused rather than allowed to empty the table. `WHERE true` keeps
-- pg-safeupdate, which Supabase enables for API requests, from rejecting a
-- DELETE with no WHERE clause.
CREATE FUNCTION replace_approved_therapies(payload jsonb) RETURNS void
LANGUAGE plpgsql
SET search_path = public, pg_temp
AS $$
BEGIN
  IF coalesce(jsonb_array_length(payload), 0) = 0 THEN
    RAISE EXCEPTION 'replace_approved_therapies: empty payload';
  END IF;
  DELETE FROM approved_therapies WHERE true;
  INSERT INTO approved_therapies
    SELECT * FROM jsonb_populate_recordset(null::approved_therapies, payload);
END;
$$;

-- New functions are executable by everyone, including anonymous API callers,
-- by default. Only the loader's secret key may run this one.
REVOKE EXECUTE ON FUNCTION replace_approved_therapies(jsonb) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION replace_approved_therapies(jsonb) TO service_role;
