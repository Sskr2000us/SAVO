-- Add metadata column to detected_ingredients (idempotent)
-- Date: 2026-01-11

BEGIN;

ALTER TABLE IF EXISTS public.detected_ingredients
    ADD COLUMN IF NOT EXISTS metadata JSONB;

-- Best-effort default for new rows.
ALTER TABLE IF EXISTS public.detected_ingredients
    ALTER COLUMN metadata SET DEFAULT '{}'::jsonb;

-- Optional index for querying metadata (safe to skip if not needed yet).
DO $$
BEGIN
    IF to_regclass('public.detected_ingredients') IS NOT NULL THEN
        CREATE INDEX IF NOT EXISTS idx_detected_ingredients_metadata_gin
            ON public.detected_ingredients
            USING GIN (metadata);
    END IF;
END
$$;

COMMIT;
