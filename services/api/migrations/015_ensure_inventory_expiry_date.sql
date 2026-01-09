-- Ensure inventory_items has expiry_date column (idempotent)
-- Some older deployments may not have this column; without it, expiry-date edits will be silently dropped.

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'inventory_items'
      AND column_name = 'expiry_date'
  ) THEN
    ALTER TABLE public.inventory_items
      ADD COLUMN expiry_date DATE;
  END IF;
END $$;

-- Helpful index for expiring/expiry queries (idempotent)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_indexes
    WHERE schemaname = 'public'
      AND indexname = 'idx_inventory_expiry'
  ) THEN
    CREATE INDEX idx_inventory_expiry
      ON public.inventory_items(user_id, expiry_date)
      WHERE expiry_date IS NOT NULL;
  END IF;
END $$;
