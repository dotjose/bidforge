-- Vector similarity search for RAG (1536-d embeddings, e.g. text-embedding-3-small)
create or replace function public.match_documents(
  query_embedding vector(1536),
  match_count int,
  filter_user_id uuid
)
returns table (
  id uuid,
  content text,
  metadata jsonb,
  similarity float
)
language sql
stable
as $$
  select
    d.id,
    d.content,
    d.metadata,
    (1 - (d.embedding <=> query_embedding))::float as similarity
  from public.documents d
  where d.embedding is not null
    and filter_user_id is not null
    and d.user_id = filter_user_id
  order by d.embedding <=> query_embedding
  limit greatest(1, least(match_count, 50));
$$;
