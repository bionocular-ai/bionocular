-- Columns produced by the publications LLM-as-a-Judge validation pass.
--
-- is_lt mirrors the existing is_nr pattern: a censored source value like "<1%" is
-- stored as the bound (1) so it still plots, and the column name is listed here so
-- the "<" is not lost. Written by scripts/replace_publications_supabase.py.
--
-- validation_status / validated_at record whether a row's cells were checked against
-- the source document. Rows never validated stay NULL; Batch-I_24 is 'unvalidated'
-- because its judge run timed out.
alter table public.trial_outcomes
  add column if not exists is_lt text[] null,
  add column if not exists validation_status text null,
  add column if not exists validated_at timestamp with time zone null;
