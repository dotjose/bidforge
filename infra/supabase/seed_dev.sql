-- Dev sample rows — run once in Supabase SQL editor (safe to re-run after deleting test rows)

insert into public.freelance_win_memory (
  user_id,
  job_type,
  opening_hook,
  winning_sections,
  score,
  extracted_patterns
)
select
  'test_user',
  'upwork',
  'I’ve built Elementor affiliate sites where homepage structure directly increased CTR into product pages.',
  '[]'::jsonb,
  87,
  '{"structure_pattern": "hook → intent → approach → relevance → CTA"}'::jsonb
where not exists (
  select 1 from public.freelance_win_memory m where m.user_id = 'test_user' and m.score = 87 and m.opening_hook like '%Elementor%'
);

insert into public.proposal_runs (
  user_id,
  rfp_input,
  proposal_output,
  score,
  issues,
  title,
  trace_id,
  pipeline_mode
)
select
  'test_user',
  'Sample RFP body for local testing.',
  '{"sections":{"executive_summary":"…"}}'::jsonb,
  82,
  '["CTA weak in final section"]'::jsonb,
  'Golf Gear Authority Website Conversion Optimization',
  'test_trace_001',
  'freelance'
where not exists (
  select 1 from public.proposal_runs p where p.trace_id = 'test_trace_001'
);
