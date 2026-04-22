-- BidForge core schema (run in Supabase SQL editor or via migrations)

create extension if not exists "uuid-ossp";
create extension if not exists vector;

-- Clerk user id maps to our users row
create table if not exists public.users (
  id uuid primary key default uuid_generate_v4 (),
  clerk_user_id text not null unique,
  email text,
  created_at timestamptz not null default now()
);

create table if not exists public.profiles (
  id uuid primary key default uuid_generate_v4 (),
  user_id uuid not null references public.users (id) on delete cascade,
  company_name text,
  services text,
  strengths text,
  methodology text,
  updated_at timestamptz not null default now(),
  unique (user_id)
);

create table if not exists public.proposals (
  id uuid primary key default uuid_generate_v4 (),
  user_id uuid not null references public.users (id) on delete cascade,
  title text,
  job_description text,
  body text,
  score int,
  issues jsonb default '[]'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.logs (
  id bigserial primary key,
  user_id uuid references public.users (id) on delete set null,
  level text not null,
  message text not null,
  meta jsonb default '{}'::jsonb,
  created_at timestamptz not null default now()
);

-- RAG: chunked documents with embeddings
create table if not exists public.documents (
  id uuid primary key default uuid_generate_v4 (),
  user_id uuid not null references public.users (id) on delete cascade,
  source text,
  content text not null,
  embedding vector (1536),
  metadata jsonb default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists documents_embedding_idx on public.documents
using ivfflat (embedding vector_cosine_ops)
with (lists = 100);

-- Persisted proposal generations (Clerk user id; single source of truth for history)
create table if not exists public.proposal_runs (
  id uuid primary key default uuid_generate_v4 (),
  user_id text not null,
  rfp_input text not null,
  proposal_output jsonb not null default '{}'::jsonb,
  score int not null default 0,
  issues jsonb not null default '[]'::jsonb,
  title text not null default '',
  trace_id text not null,
  pipeline_mode text not null default 'enterprise',
  created_at timestamptz not null default now ()
);

create index if not exists proposal_runs_user_created_idx on public.proposal_runs (user_id, created_at desc);
create index if not exists proposal_runs_trace_idx on public.proposal_runs (trace_id);

-- Freelance win memory layer (hooks, sections, patterns; optional embedding for future RAG)
create table if not exists public.freelance_win_memory (
  id uuid primary key default uuid_generate_v4 (),
  user_id text not null,
  job_type text not null default 'upwork',
  opening_hook text not null default '',
  winning_sections jsonb not null default '[]'::jsonb,
  score int not null default 0,
  extracted_patterns jsonb not null default '{}'::jsonb,
  embedding vector (1536),
  created_at timestamptz not null default now ()
);

create index if not exists freelance_win_memory_user_score_idx on public.freelance_win_memory (
  user_id,
  score desc,
  created_at desc
);

-- Per-user workspace preferences (tone, RAG toggles, company profile JSON)
create table if not exists public.workspace_settings (
  user_id text primary key,
  company_profile jsonb not null default '{}'::jsonb,
  tone text not null default '',
  writing_style text not null default '',
  rag_config jsonb not null default '{"enabled": true, "enterprise_case_studies": true, "freelance_win_memory": true}'::jsonb,
  updated_at timestamptz not null default now ()
);

-- Optional: create a vector index after you have sufficient rows with non-null embeddings.
-- create index freelance_win_memory_embedding_idx on public.freelance_win_memory
-- using ivfflat (embedding vector_cosine_ops) with (lists = 50);

-- Snippets from completed proposals (optional embedding for future retrieval)
create table if not exists public.proposal_memory (
  id uuid primary key default uuid_generate_v4 (),
  user_id uuid not null references public.users (id) on delete cascade,
  snippet text not null,
  type text not null,
  embedding vector (1536),
  created_at timestamptz not null default now (),
  constraint proposal_memory_type_chk check (type in ('win_pattern', 'strong_line'))
);

create index if not exists proposal_memory_user_created_idx on public.proposal_memory (user_id, created_at desc);
