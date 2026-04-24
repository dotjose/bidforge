-- Idempotent core tables for BidForge (run in Supabase SQL editor or CI).
-- Requires service role for DDL; app uses SUPABASE_SERVICE_ROLE_KEY for reads/writes.

create extension if not exists "pgcrypto";

-- Pipeline runs (matches api insert_proposal_run)
create table if not exists public.proposals (
  id uuid primary key default gen_random_uuid(),
  user_id text not null,
  rfp_text text,
  proposal_content jsonb not null default '{}'::jsonb,
  pipeline_state jsonb not null default '{}'::jsonb,
  settings_snapshot jsonb not null default '{}'::jsonb,
  pattern text,
  title text,
  score integer not null default 0,
  issues jsonb not null default '[]'::jsonb,
  trace_id text not null,
  pipeline_mode text not null default 'enterprise',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists proposals_user_id_created_at_idx
  on public.proposals (user_id, created_at desc);

create index if not exists proposals_trace_id_idx
  on public.proposals (trace_id);

-- Dynamic RFP/job-type templates (optional; drives generation)
create table if not exists public.proposal_templates (
  id uuid primary key default gen_random_uuid(),
  user_id text not null,
  detected_type text not null default '',
  template_structure jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists proposal_templates_user_created_idx
  on public.proposal_templates (user_id, created_at desc);

-- Freelance win memory: optional normalized columns (legacy rows still work)
alter table if exists public.freelance_win_memory
  add column if not exists pattern_type text;

alter table if exists public.freelance_win_memory
  add column if not exists content text;

comment on column public.freelance_win_memory.pattern_type is 'hook | proof | cta when extracted from a win';
comment on column public.freelance_win_memory.content is 'Short pattern text when not using opening_hook only';
