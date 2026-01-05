-- Permanent receipt-scan support: add receipt_scans table + inventory_items.last_seen_receipt_id
-- Keeps the existing last_seen_scan_id FK to ingredient_scans for pantry/photo scans.

BEGIN;

-- 1) receipt_scans table (idempotent)
CREATE TABLE IF NOT EXISTS public.receipt_scans (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    image_url TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_receipt_scans_user_created
    ON public.receipt_scans(user_id, created_at DESC);

ALTER TABLE public.receipt_scans ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname='public' AND tablename='receipt_scans' AND policyname='Users can view own receipt scans'
    ) THEN
        CREATE POLICY "Users can view own receipt scans" ON public.receipt_scans
            FOR SELECT
            TO authenticated
            USING (auth.uid() = user_id);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname='public' AND tablename='receipt_scans' AND policyname='Users can insert own receipt scans'
    ) THEN
        CREATE POLICY "Users can insert own receipt scans" ON public.receipt_scans
            FOR INSERT
            TO authenticated
            WITH CHECK (auth.uid() = user_id);
    END IF;
END $$;

GRANT SELECT, INSERT, UPDATE ON public.receipt_scans TO authenticated;

-- 2) inventory_items.last_seen_receipt_id + FK to receipt_scans
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema='public' AND table_name='inventory_items' AND column_name='last_seen_receipt_id'
    ) THEN
        ALTER TABLE public.inventory_items
            ADD COLUMN last_seen_receipt_id UUID NULL;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'inventory_items_last_seen_receipt_id_fkey'
    ) THEN
        ALTER TABLE public.inventory_items
            ADD CONSTRAINT inventory_items_last_seen_receipt_id_fkey
            FOREIGN KEY (last_seen_receipt_id) REFERENCES public.receipt_scans(id) ON DELETE SET NULL;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_inventory_items_user_last_seen_receipt
    ON public.inventory_items(user_id, last_seen_receipt_id);

COMMIT;
