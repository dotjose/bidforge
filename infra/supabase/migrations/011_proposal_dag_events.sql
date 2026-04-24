-- DAG observability + per-node cache (append-only events; cache is lookup only).
-- Apply in the same Supabase project as public.proposals.

create table if not exists public.proposal_events (
  id uuid primary key default gen_random_uuid(),
  user_id text not null,
  trace_id text not null,
  proposal_id uuid null,
  node_id text not null,
  parent_node_id text not null default '',
  input_hash text not null,
  output_hash text not null,
  model_used text not null default '',
  token_usage jsonb not null default '{}'::jsonb,
  latency_ms integer not null default 0,
  deterministic_version_id text not null default '',
  cache_key text not null default '',
  retries integer not null default 0,
  version text not null default '',
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists proposal_events_trace_id_idx
  on public.proposal_events (trace_id);

create index if not exists proposal_events_user_created_idx
  on public.proposal_events (user_id, created_at desc);

create index if not exists proposal_events_proposal_id_idx
  on public.proposal_events (proposal_id);

create table if not exists public.proposal_node_cache (
  cache_key text primary key,
  output_hash text not null,
  output jsonb not null,
  created_at timestamptz not null default now()
);

create index if not exists proposal_node_cache_created_idx
  on public.proposal_node_cache (created_at desc);
