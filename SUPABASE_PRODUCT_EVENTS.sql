-- Product analytics events (activation funnel)
-- Apply in Supabase SQL editor.

create table if not exists public.product_events (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null,
  event_name text not null,
  event_ts timestamptz not null default now(),
  props jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists product_events_user_ts_idx
  on public.product_events (user_id, event_ts desc);

create index if not exists product_events_name_ts_idx
  on public.product_events (event_name, event_ts desc);

-- Enable RLS and allow the service role / API to insert.
alter table public.product_events enable row level security;

-- Note: If your API uses the service role key, it can bypass RLS.
-- Otherwise, you can add policies as needed.
