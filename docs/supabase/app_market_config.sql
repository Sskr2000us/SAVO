-- SAVO Market Config (Feature Flags + Retailers)
-- Purpose: region/country scoped rollout + retailer configuration for Shopping Cart.
-- Apply in Supabase SQL editor.

create extension if not exists pgcrypto;

-- Feature flags per region
create table if not exists public.app_feature_flags (
  id uuid primary key default gen_random_uuid(),
  region text not null,
  feature_key text not null,
  enabled boolean not null default false,
  payload jsonb null,
  updated_at timestamptz not null default now()
);

create unique index if not exists app_feature_flags_region_key
  on public.app_feature_flags (region, feature_key);

-- Optional: mark super admins in public.users (backend also supports env allowlist)
alter table public.users
  add column if not exists is_super_admin boolean not null default false;

-- Retailers per region (for Shopping Cart integrations)
create table if not exists public.app_retailers (
  id uuid primary key default gen_random_uuid(),
  region text not null,
  name text not null,
  url text null,
  enabled boolean not null default true,
  sort_order integer not null default 0,
  updated_at timestamptz not null default now()
);

create unique index if not exists app_retailers_region_name
  on public.app_retailers (region, name);

-- Recommended seed examples:
-- insert into public.app_feature_flags (region, feature_key, enabled)
-- values ('US', 'shopping_cart', true)
-- on conflict (region, feature_key) do update set enabled = excluded.enabled, updated_at = now();

-- Example: enable shareable recipe links in US
-- insert into public.app_feature_flags (region, feature_key, enabled)
-- values ('US', 'shareable_recipes', true)
-- on conflict (region, feature_key) do update set enabled = excluded.enabled, updated_at = now();
