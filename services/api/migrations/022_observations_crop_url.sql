-- Add crop references to scan observations (idempotent)
-- Date: 2026-01-09

DO $$
BEGIN
    -- Add to underlying table
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema='observations' AND table_name='scan_observations'
    ) THEN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema='observations' AND table_name='scan_observations' AND column_name='crop_url'
        ) THEN
            ALTER TABLE observations.scan_observations
                ADD COLUMN crop_url TEXT NULL;
        END IF;
    END IF;

    -- Recreate public view to pick up new column
    BEGIN
        EXECUTE 'DROP VIEW IF EXISTS public.scan_observations';
        EXECUTE 'CREATE VIEW public.scan_observations WITH (security_invoker=true) AS SELECT * FROM observations.scan_observations';
    EXCEPTION WHEN OTHERS THEN
        BEGIN
            EXECUTE 'DROP VIEW IF EXISTS public.scan_observations';
            EXECUTE 'CREATE VIEW public.scan_observations AS SELECT * FROM observations.scan_observations';
        EXCEPTION WHEN OTHERS THEN
            NULL;
        END;
    END;
END $$;
