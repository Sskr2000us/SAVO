-- Saved Recipes (per-user recipe library)
-- Apply this in Supabase SQL editor.

create table if not exists public.saved_recipes (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null,
  recipe_id text not null,
  recipe jsonb not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index if not exists saved_recipes_user_recipe_uidx
  on public.saved_recipes(user_id, recipe_id);

-- Basic RLS: users can only access their own rows
alter table public.saved_recipes enable row level security;

do $$
begin
  if not exists (
    select 1 from pg_policies
    where schemaname = 'public'
      and tablename = 'saved_recipes'
      and policyname = 'saved_recipes_select_own'
  ) then
    create policy saved_recipes_select_own
      on public.saved_recipes
      for select
      using (auth.uid() = user_id);
  end if;

  if not exists (
    select 1 from pg_policies
    where schemaname = 'public'
      and tablename = 'saved_recipes'
      and policyname = 'saved_recipes_insert_own'
  ) then
    create policy saved_recipes_insert_own
      on public.saved_recipes
      for insert
      with check (auth.uid() = user_id);
  end if;

  if not exists (
    select 1 from pg_policies
    where schemaname = 'public'
      and tablename = 'saved_recipes'
      and policyname = 'saved_recipes_delete_own'
  ) then
    create policy saved_recipes_delete_own
      on public.saved_recipes
      for delete
      using (auth.uid() = user_id);
  end if;

  if not exists (
    select 1 from pg_policies
    where schemaname = 'public'
      and tablename = 'saved_recipes'
      and policyname = 'saved_recipes_update_own'
  ) then
    create policy saved_recipes_update_own
      on public.saved_recipes
      for update
      using (auth.uid() = user_id)
      with check (auth.uid() = user_id);
  end if;
end $$;
