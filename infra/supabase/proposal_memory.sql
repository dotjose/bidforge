-- Indexed snippets from completed proposals (tenant-scoped, optional embedding for future RAG).
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
