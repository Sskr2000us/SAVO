-- Household-synced Shopping List (SAVO)
-- Purpose: realtime, multi-device collaboration for a single household.
-- This policy set assumes ONE authenticated Supabase user owns the household (household_profiles.user_id).
-- If you later add multiple authenticated users per household, adjust the RLS policy to check membership.

create extension if not exists pgcrypto;

create table if not exists public.household_shopping_items (
  id uuid primary key default gen_random_uuid(),
  household_id uuid not null,
  item_key text not null,
  item_json jsonb not null,
  checked boolean not null default false,
  created_by uuid null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index if not exists household_shopping_items_household_key
  on public.household_shopping_items (household_id, item_key);

-- (Optional) FK if your household_profiles.id exists and is uuid.
-- alter table public.household_shopping_items
--   add constraint household_shopping_items_household_fk
--   foreign key (household_id) references public.household_profiles (id)
--   on delete cascade;

alter table public.household_shopping_items enable row level security;

-- Owner-only policies (supports multi-device via same login)
create policy "shopping_items_select_own_household"
  on public.household_shopping_items
  for select
  using (
    exists (
      select 1
      from public.household_profiles hp
      where hp.id = household_shopping_items.household_id
        and hp.user_id = auth.uid()
    )
  );

create policy "shopping_items_insert_own_household"
  on public.household_shopping_items
  for insert
  with check (
    exists (
      select 1
      from public.household_profiles hp
      where hp.id = household_shopping_items.household_id
        and hp.user_id = auth.uid()
    )
  );

create policy "shopping_items_update_own_household"
  on public.household_shopping_items
  for update
  using (
    exists (
      select 1
      from public.household_profiles hp
      where hp.id = household_shopping_items.household_id
        and hp.user_id = auth.uid()
    )
  )
  with check (
    exists (
      select 1
      from public.household_profiles hp
      where hp.id = household_shopping_items.household_id
        and hp.user_id = auth.uid()
    )
  );

create policy "shopping_items_delete_own_household"
  on public.household_shopping_items
  for delete
  using (
    exists (
      select 1
      from public.household_profiles hp
      where hp.id = household_shopping_items.household_id
        and hp.user_id = auth.uid()
    )
  );

-- Realtime:
-- In Supabase dashboard -> Database -> Replication -> enable Realtime for this table.
-- Also ensure your API settings allow Realtime and RLS policies above are in place.
