-- Add subcategory to inventory_items (idempotent)

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'inventory_items'
          AND column_name = 'subcategory'
    ) THEN
        ALTER TABLE public.inventory_items
            ADD COLUMN subcategory TEXT;
    END IF;
EXCEPTION
    WHEN others THEN NULL;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_indexes
        WHERE schemaname = 'public'
          AND tablename = 'inventory_items'
          AND indexname = 'idx_inventory_items_user_category_subcategory'
    ) THEN
        CREATE INDEX idx_inventory_items_user_category_subcategory
            ON public.inventory_items(user_id, category, subcategory);
    END IF;
EXCEPTION
    WHEN others THEN NULL;
END $$;
