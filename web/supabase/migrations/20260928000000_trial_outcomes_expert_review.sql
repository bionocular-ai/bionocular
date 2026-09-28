-- A pharmacology expert's check of a row against its source document.
--
-- Separate from validation_status, which records the LLM-as-a-Judge pass: this
-- is a human verdict, and the agent's answer table lets the reader filter to it.
-- 'good' means the row matches its source; 'issues' means the expert found
-- errors in it. Rows never reviewed stay NULL. Written by
-- melanoma/scripts/record_expert_review.py, one source (abstract or
-- publication) at a time, so every arm of a reviewed source carries the verdict.
alter table public.trial_outcomes
  add column if not exists expert_review text null
    constraint trial_outcomes_expert_review_check check (expert_review in ('good', 'issues')),
  add column if not exists expert_reviewed_at timestamp with time zone null;
