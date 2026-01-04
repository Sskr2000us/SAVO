-- SAVO Shareable Recipes
-- Purpose: store shareable recipe payloads for deep links and public web pages.
-- Apply in Supabase SQL editor.

create extension if not exists pgcrypto;

create table if not exists public.shared_recipes (
  id uuid primary key default gen_random_uuid(),
  owner_user_id uuid not null,
  recipe jsonb not null,
  created_at timestamptz not null default now(),
  expires_at timestamptz null
);

create index if not exists shared_recipes_expires_at_idx
  on public.shared_recipes (expires_at);

create index if not exists shared_recipes_owner_idx
  on public.shared_recipes (owner_user_id);

-- Recommended: keep RLS on (no direct client access needed; backend uses service key)
alter table public.shared_recipes enable row level security;

-- (Optional) If you later want authenticated users to read their own shares directly:
-- create policy "read own shared recipes" on public.shared_recipes
--   for select using (auth.uid() = owner_user_id);
