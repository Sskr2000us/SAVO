-- Add product-identification fields to inventory_items (idempotent)
--
-- Supports barcode-based capture and storing product images/pack sizes.

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'inventory_items'
          AND column_name = 'barcode'
    ) THEN
        ALTER TABLE public.inventory_items
            ADD COLUMN barcode TEXT;
        CREATE INDEX IF NOT EXISTS idx_inventory_items_barcode
            ON public.inventory_items(user_id, barcode)
            WHERE barcode IS NOT NULL;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'inventory_items'
          AND column_name = 'product_name'
    ) THEN
        ALTER TABLE public.inventory_items
            ADD COLUMN product_name TEXT;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'inventory_items'
          AND column_name = 'brand'
    ) THEN
        ALTER TABLE public.inventory_items
            ADD COLUMN brand TEXT;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'inventory_items'
          AND column_name = 'image_url'
    ) THEN
        ALTER TABLE public.inventory_items
            ADD COLUMN image_url TEXT;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'inventory_items'
          AND column_name = 'package_size_text'
    ) THEN
        ALTER TABLE public.inventory_items
            ADD COLUMN package_size_text TEXT;
    END IF;
END $$;
