-- Shared meal plans (for Coach dashboard / plan sharing)
-- Create a table to store shareable plan payloads server-side.

create table if not exists public.shared_plans (
  id uuid primary key,
  owner_user_id uuid not null,
  plan jsonb not null,
  created_at timestamptz not null default now(),
  expires_at timestamptz not null
);

create index if not exists idx_shared_plans_owner on public.shared_plans(owner_user_id);
create index if not exists idx_shared_plans_expires on public.shared_plans(expires_at);
