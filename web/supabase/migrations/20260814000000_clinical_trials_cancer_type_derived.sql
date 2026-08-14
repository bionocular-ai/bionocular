-- Shadow columns for the conditions-derived cancer_type.
--
-- `cancer_type` today is a byproduct of the ClinicalTrials.gov search term that
-- discovered the trial, not a fact about the trial. `query.cond=Cutaneous melanoma`
-- resolves through the MeSH synonym thesaurus to D008545 Melanoma and returns 3708 of
-- the registry's 3746 melanoma studies, so every uveal, acral and mucosal trial is
-- tagged cutaneous as well.
--
-- `cancer_type_derived` is computed from the trial's own conditionsModule.conditions by
-- src/infrastructure/clinical_trials/cancer_type_derivation.py. It is written alongside
-- the existing value, never over it: the backfill, the validation pass and the promote
-- step are separate, and nothing reads these columns until the promote lands.
--
-- `cancer_type_evidence` maps each derived bucket to the verbatim condition string that
-- produced it, so a reviewer or the chat agent can quote the justification instead of
-- asserting the tag.
--
-- `is_basket` marks multi-tumour or non-specific trials (conditions such as 'Cancer' or
-- 'Advanced Solid Tumor'). `melanoma_unspecified` marks trials naming melanoma with no
-- subtype and no cutaneous/skin qualifier - true for roughly 73% of the melanoma bucket,
-- so it drives a group-level caveat rather than a per-trial one.
alter table public.clinical_trials
  add column if not exists cancer_type_derived text[] null,
  add column if not exists cancer_type_evidence jsonb null,
  add column if not exists is_basket boolean null,
  add column if not exists melanoma_unspecified boolean null;
