-- Canonical persisted source for each proposal run (reproducibility / regeneration).
-- App writes `input_text` + legacy `rfp_text` to the same value until all clients use `input_text` only.

alter table if exists public.proposals
  add column if not exists input_text text;

alter table if exists public.proposals
  add column if not exists input_type text;

update public.proposals
set input_text = coalesce(nullif(trim(input_text), ''), rfp_text, '')
where input_text is null or trim(coalesce(input_text, '')) = '';

update public.proposals
set rfp_text = coalesce(nullif(trim(rfp_text), ''), input_text, '')
where rfp_text is null or trim(coalesce(rfp_text, '')) = '';

comment on column public.proposals.input_text is 'Original RFP / job post (source of truth for regeneration; never derive from proposal_content only).';
comment on column public.proposals.input_type is 'Classifier input_type (e.g. rfp, job_post) at run time.';
