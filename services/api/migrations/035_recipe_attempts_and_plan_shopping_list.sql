-- Recipe attempts persistence + meal plan shopping list
-- Date: 2026-01-11
-- Purpose:
--  - Persist recipe generation attempts (inputs + outputs) for saving and planning
--  - Add an optional meal_plans.shopping_list JSONB column

DO $do$
BEGIN
    -- Create recipe_attempts (additive)
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema='public' AND table_name='recipe_attempts'
    ) THEN
        CREATE TABLE public.recipe_attempts (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,

            recipe_id TEXT NOT NULL,
            request_text TEXT,

            mode TEXT NOT NULL,
            reason TEXT NOT NULL,
            pantry_coverage DOUBLE PRECISION,

            locked_constraints JSONB NOT NULL DEFAULT '{}'::jsonb,
            family_profile JSONB NOT NULL DEFAULT '{}'::jsonb,
            pantry_context JSONB NOT NULL DEFAULT '[]'::jsonb,
            missing_ingredients JSONB NOT NULL DEFAULT '[]'::jsonb,
            recipe JSONB NOT NULL DEFAULT '{}'::jsonb,
            image_signals JSONB NOT NULL DEFAULT '[]'::jsonb,

            saved BOOLEAN NOT NULL DEFAULT FALSE,
            saved_at TIMESTAMPTZ,

            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    END IF;

    -- Add optional shopping_list column to meal_plans
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema='public' AND table_name='meal_plans'
    ) THEN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema='public' AND table_name='meal_plans' AND column_name='shopping_list'
        ) THEN
            ALTER TABLE public.meal_plans
                ADD COLUMN shopping_list JSONB NOT NULL DEFAULT '[]'::jsonb;
        END IF;
    END IF;

    -- Indexes (best-effort; guard by pg_class)
    IF NOT EXISTS (
        SELECT 1
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname='public' AND c.relname='idx_recipe_attempts_user_created'
    ) THEN
        CREATE INDEX idx_recipe_attempts_user_created ON public.recipe_attempts(user_id, created_at DESC);
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname='public' AND c.relname='idx_recipe_attempts_user_recipe'
    ) THEN
        CREATE INDEX idx_recipe_attempts_user_recipe ON public.recipe_attempts(user_id, recipe_id, created_at DESC);
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname='public' AND c.relname='idx_recipe_attempts_user_saved'
    ) THEN
        CREATE INDEX idx_recipe_attempts_user_saved ON public.recipe_attempts(user_id, saved, saved_at DESC);
    END IF;

    -- updated_at trigger if the shared function exists
    IF EXISTS (SELECT 1 FROM pg_proc WHERE proname='update_updated_at_column') THEN
        IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='update_recipe_attempts_updated_at') THEN
            CREATE TRIGGER update_recipe_attempts_updated_at
                BEFORE UPDATE ON public.recipe_attempts
                FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
        END IF;
    END IF;
END $do$;
