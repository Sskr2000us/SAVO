-- Add confidence column to user_pantry (idempotent - safe to re-run)
--
-- Background:
-- The application may compute a confidence score for pantry items.
-- Some code paths previously attempted to write `confidence` into user_pantry,
-- but the base table schema did not include it.

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'user_pantry'
          AND column_name = 'confidence'
    ) THEN
        ALTER TABLE public.user_pantry
            ADD COLUMN confidence DOUBLE PRECISION;

        ALTER TABLE public.user_pantry
            ADD CONSTRAINT user_pantry_confidence_range
            CHECK (confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0));

        COMMENT ON COLUMN public.user_pantry.confidence IS 'Confidence score (0..1) for the pantry item source/quantity. Manual entries are typically 1.0.';
    END IF;
END $$;
