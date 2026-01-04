-- Migration: Inventory current-scan tracking
-- Adds fields to mark which inventory items are part of the latest scan set.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema='public' AND table_name='inventory_items' AND column_name='is_current'
    ) THEN
        ALTER TABLE public.inventory_items
            ADD COLUMN is_current BOOLEAN NOT NULL DEFAULT TRUE;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema='public' AND table_name='inventory_items' AND column_name='last_seen_at'
    ) THEN
        ALTER TABLE public.inventory_items
            ADD COLUMN last_seen_at TIMESTAMPTZ NULL;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema='public' AND table_name='inventory_items' AND column_name='last_seen_scan_id'
    ) THEN
        ALTER TABLE public.inventory_items
            ADD COLUMN last_seen_scan_id UUID NULL;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'inventory_items_last_seen_scan_id_fkey'
    ) THEN
        ALTER TABLE public.inventory_items
            ADD CONSTRAINT inventory_items_last_seen_scan_id_fkey
            FOREIGN KEY (last_seen_scan_id) REFERENCES public.ingredient_scans(id) ON DELETE SET NULL;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_inventory_items_user_current
    ON public.inventory_items(user_id, is_current, updated_at DESC);

COMMIT;
