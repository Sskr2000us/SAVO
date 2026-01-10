-- Add scan session correlation fields
-- Date: 2026-01-09
-- Purpose:
--  - Persist session_id + correlation_id on scan records for audit/debug

DO $$
BEGIN
    -- ingredient_scans: link scans to scan_sessions
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema='public'
          AND table_name='ingredient_scans'
          AND column_name='session_id'
    ) THEN
        ALTER TABLE public.ingredient_scans
            ADD COLUMN session_id UUID;
        CREATE INDEX IF NOT EXISTS idx_ingredient_scans_session_id ON public.ingredient_scans(session_id);
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema='public'
          AND table_name='ingredient_scans'
          AND column_name='correlation_id'
    ) THEN
        ALTER TABLE public.ingredient_scans
            ADD COLUMN correlation_id TEXT;
        CREATE INDEX IF NOT EXISTS idx_ingredient_scans_correlation_id ON public.ingredient_scans(correlation_id);
    END IF;

    -- detected_ingredients: duplicate correlation for easy auditing without joins
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema='public'
          AND table_name='detected_ingredients'
          AND column_name='session_id'
    ) THEN
        ALTER TABLE public.detected_ingredients
            ADD COLUMN session_id UUID;
        CREATE INDEX IF NOT EXISTS idx_detected_ingredients_session_id ON public.detected_ingredients(session_id);
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema='public'
          AND table_name='detected_ingredients'
          AND column_name='correlation_id'
    ) THEN
        ALTER TABLE public.detected_ingredients
            ADD COLUMN correlation_id TEXT;
        CREATE INDEX IF NOT EXISTS idx_detected_ingredients_correlation_id ON public.detected_ingredients(correlation_id);
    END IF;
END $$;
