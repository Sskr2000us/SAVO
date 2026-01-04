-- Add household shopping list items table (Supabase realtime sync)
-- Created: 2026-01-04
-- Purpose: Backing store for Shopping List so multiple devices can stay in sync.

-- Uses a composite primary key so client-side upserts work without specifying on_conflict.
CREATE TABLE IF NOT EXISTS public.household_shopping_items (
    household_id UUID NOT NULL REFERENCES public.household_profiles(id) ON DELETE CASCADE,
    item_key TEXT NOT NULL,
    item_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    checked BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    PRIMARY KEY (household_id, item_key)
);

-- If the table already exists (e.g., created manually), ensure required columns exist.
ALTER TABLE public.household_shopping_items
    ADD COLUMN IF NOT EXISTS item_json JSONB NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE public.household_shopping_items
    ADD COLUMN IF NOT EXISTS checked BOOLEAN NOT NULL DEFAULT false;

ALTER TABLE public.household_shopping_items
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();

ALTER TABLE public.household_shopping_items
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

CREATE INDEX IF NOT EXISTS idx_household_shopping_items_household_updated
    ON public.household_shopping_items(household_id, updated_at DESC);

-- Keep updated_at fresh on updates.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger
        WHERE tgname = 'update_household_shopping_items_updated_at'
    ) THEN
        CREATE TRIGGER update_household_shopping_items_updated_at BEFORE UPDATE ON public.household_shopping_items
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    END IF;
END;
$$;

-- Row Level Security (aligns with household-scoped policies used elsewhere).
ALTER TABLE public.household_shopping_items ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename = 'household_shopping_items'
          AND policyname = 'Users can view own household shopping items'
    ) THEN
        CREATE POLICY "Users can view own household shopping items" ON public.household_shopping_items
            FOR SELECT USING (
                household_id IN (
                    SELECT id FROM public.household_profiles WHERE user_id = auth.uid()
                )
            );
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename = 'household_shopping_items'
          AND policyname = 'Users can insert own household shopping items'
    ) THEN
        CREATE POLICY "Users can insert own household shopping items" ON public.household_shopping_items
            FOR INSERT WITH CHECK (
                household_id IN (
                    SELECT id FROM public.household_profiles WHERE user_id = auth.uid()
                )
            );
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename = 'household_shopping_items'
          AND policyname = 'Users can update own household shopping items'
    ) THEN
        CREATE POLICY "Users can update own household shopping items" ON public.household_shopping_items
            FOR UPDATE USING (
                household_id IN (
                    SELECT id FROM public.household_profiles WHERE user_id = auth.uid()
                )
            );
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename = 'household_shopping_items'
          AND policyname = 'Users can delete own household shopping items'
    ) THEN
        CREATE POLICY "Users can delete own household shopping items" ON public.household_shopping_items
            FOR DELETE USING (
                household_id IN (
                    SELECT id FROM public.household_profiles WHERE user_id = auth.uid()
                )
            );
    END IF;
END;
$$;
