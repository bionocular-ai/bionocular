-- Rename nct_id (text) → nct_ids (text[])
ALTER TABLE news_feed RENAME COLUMN nct_id TO nct_ids;
ALTER TABLE news_feed
  ALTER COLUMN nct_ids TYPE text[]
    USING CASE WHEN nct_ids IS NULL THEN NULL ELSE ARRAY[nct_ids] END;

-- cancer_type (text) → cancer_type (text[]) — articles can match multiple types
ALTER TABLE news_feed
  ALTER COLUMN cancer_type TYPE text[]
    USING CASE WHEN cancer_type IS NULL THEN NULL ELSE ARRAY[cancer_type] END;

-- New columns
ALTER TABLE news_feed
  ADD COLUMN IF NOT EXISTS source        text,
  ADD COLUMN IF NOT EXISTS has_efficacy  boolean DEFAULT false,
  ADD COLUMN IF NOT EXISTS efficacy_data jsonb,
  ADD COLUMN IF NOT EXISTS has_safety    boolean DEFAULT false,
  ADD COLUMN IF NOT EXISTS safety_data   jsonb,
  ADD COLUMN IF NOT EXISTS extracted_at  timestamptz;

-- Deduplicate existing rows by URL before adding unique index, keep latest id
DELETE FROM news_feed
WHERE id NOT IN (
  SELECT MAX(id) FROM news_feed GROUP BY url
);

-- Unique index for idempotent upsert on URL (ON CONFLICT url)
CREATE UNIQUE INDEX IF NOT EXISTS news_feed_url_key ON news_feed (url);
