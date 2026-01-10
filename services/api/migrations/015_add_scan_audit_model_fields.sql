-- Add model version + reference image audit fields (idempotent)
-- Date: 2026-01-09
-- Purpose:
--  - Store the vision model version/provider used for scan-derived inventory items
--  - Store a stable reference to the detected ingredient used as the reference image

DO $$
BEGIN
    -- inventory_items: audit fields
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'inventory_items'
          AND column_name = 'model_version'
    ) THEN
        ALTER TABLE public.inventory_items
            ADD COLUMN model_version TEXT;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'inventory_items'
          AND column_name = 'model_provider'
    ) THEN
        ALTER TABLE public.inventory_items
            ADD COLUMN model_provider TEXT;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'inventory_items'
          AND column_name = 'reference_detected_id'
    ) THEN
        ALTER TABLE public.inventory_items
            ADD COLUMN reference_detected_id UUID;
    END IF;

    -- ingredient_scans: model version used
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'ingredient_scans'
          AND column_name = 'model_version'
    ) THEN
        ALTER TABLE public.ingredient_scans
            ADD COLUMN model_version TEXT;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'ingredient_scans'
          AND column_name = 'model_provider'
    ) THEN
        ALTER TABLE public.ingredient_scans
            ADD COLUMN model_provider TEXT;
    END IF;

    -- detected_ingredients: model version used
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'detected_ingredients'
          AND column_name = 'model_version'
    ) THEN
        ALTER TABLE public.detected_ingredients
            ADD COLUMN model_version TEXT;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'detected_ingredients'
          AND column_name = 'model_provider'
    ) THEN
        ALTER TABLE public.detected_ingredients
            ADD COLUMN model_provider TEXT;
    END IF;
END $$;
