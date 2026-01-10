-- Add KPI fields for scan dashboards + inventory event logging (idempotent)
-- Date: 2026-01-09
-- Purpose:
--  - Track scan processing time and confirmation outcomes per release/model
--  - Track auto-add false positives via inventory edit/delete events

DO $$
BEGIN
    -- ingredient_scans: KPI fields
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'ingredient_scans'
          AND column_name = 'release_version'
    ) THEN
        ALTER TABLE public.ingredient_scans
            ADD COLUMN release_version TEXT;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'ingredient_scans'
          AND column_name = 'app_version'
    ) THEN
        ALTER TABLE public.ingredient_scans
            ADD COLUMN app_version TEXT;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'ingredient_scans'
          AND column_name = 'analysis_ms'
    ) THEN
        ALTER TABLE public.ingredient_scans
            ADD COLUMN analysis_ms INTEGER;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'ingredient_scans'
          AND column_name = 'confirm_ms'
    ) THEN
        ALTER TABLE public.ingredient_scans
            ADD COLUMN confirm_ms INTEGER;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'ingredient_scans'
          AND column_name = 'confirmed_at'
    ) THEN
        ALTER TABLE public.ingredient_scans
            ADD COLUMN confirmed_at TIMESTAMPTZ;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'ingredient_scans'
          AND column_name = 'detected_count'
    ) THEN
        ALTER TABLE public.ingredient_scans
            ADD COLUMN detected_count INTEGER;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'ingredient_scans'
          AND column_name = 'confirmed_count'
    ) THEN
        ALTER TABLE public.ingredient_scans
            ADD COLUMN confirmed_count INTEGER;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'ingredient_scans'
          AND column_name = 'modified_count'
    ) THEN
        ALTER TABLE public.ingredient_scans
            ADD COLUMN modified_count INTEGER;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'ingredient_scans'
          AND column_name = 'rejected_count'
    ) THEN
        ALTER TABLE public.ingredient_scans
            ADD COLUMN rejected_count INTEGER;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'ingredient_scans'
          AND column_name = 'auto_added_count'
    ) THEN
        ALTER TABLE public.ingredient_scans
            ADD COLUMN auto_added_count INTEGER;
    END IF;

    -- inventory_items: release/app attribution
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'inventory_items'
          AND column_name = 'release_version'
    ) THEN
        ALTER TABLE public.inventory_items
            ADD COLUMN release_version TEXT;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'inventory_items'
          AND column_name = 'app_version'
    ) THEN
        ALTER TABLE public.inventory_items
            ADD COLUMN app_version TEXT;
    END IF;

    -- inventory_item_events: track corrections/false positives
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_name = 'inventory_item_events'
    ) THEN
        CREATE TABLE public.inventory_item_events (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL,
            item_id UUID NOT NULL,
            event_ts TIMESTAMPTZ NOT NULL DEFAULT now(),
            event_type TEXT NOT NULL,
            before JSONB,
            after JSONB,
            item_source TEXT,
            item_scan_confidence DOUBLE PRECISION,
            item_model_version TEXT,
            item_model_provider TEXT,
            item_release_version TEXT,
            item_app_version TEXT
        );

        CREATE INDEX inventory_item_events_user_ts_idx ON public.inventory_item_events(user_id, event_ts);
        CREATE INDEX inventory_item_events_item_ts_idx ON public.inventory_item_events(item_id, event_ts);
        CREATE INDEX inventory_item_events_type_ts_idx ON public.inventory_item_events(event_type, event_ts);
    END IF;
END $$;
