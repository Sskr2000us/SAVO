-- Allow 'receipt' as an inventory_items.source value (idempotent)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'inventory_items_source_check'
    ) THEN
        ALTER TABLE public.inventory_items
            DROP CONSTRAINT inventory_items_source_check;
    END IF;

    ALTER TABLE public.inventory_items
        ADD CONSTRAINT inventory_items_source_check
        CHECK (source IN ('manual', 'scan', 'import', 'receipt'));
END $$;
