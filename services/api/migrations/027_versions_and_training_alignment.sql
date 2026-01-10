-- Alignment migration: version stamps + training label privacy fields
-- Date: 2026-01-10

DO $$
BEGIN
    -- ------------------------------------------------------------------
    -- Observations: add taxonomy_version for end-to-end version stamping
    -- ------------------------------------------------------------------
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema='observations' AND table_name='scan_observations'
    ) THEN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema='observations' AND table_name='scan_observations' AND column_name='taxonomy_version'
        ) THEN
            ALTER TABLE observations.scan_observations
                ADD COLUMN taxonomy_version TEXT NULL;
        END IF;
    END IF;

    -- Keep the public view stable (recreate to pick up potential security_invoker changes)
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

    -- ------------------------------------------------------------------
    -- Training labels: add optional versioning + anonymized signatures
    -- ------------------------------------------------------------------
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema='public' AND table_name='scan_training_labels'
    ) THEN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema='public' AND table_name='scan_training_labels' AND column_name='item_signature'
        ) THEN
            ALTER TABLE public.scan_training_labels
                ADD COLUMN item_signature TEXT NULL;
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema='public' AND table_name='scan_training_labels' AND column_name='anon_user_signature'
        ) THEN
            ALTER TABLE public.scan_training_labels
                ADD COLUMN anon_user_signature TEXT NULL;
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema='public' AND table_name='scan_training_labels' AND column_name='model_version'
        ) THEN
            ALTER TABLE public.scan_training_labels
                ADD COLUMN model_version TEXT NULL;
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema='public' AND table_name='scan_training_labels' AND column_name='release_version'
        ) THEN
            ALTER TABLE public.scan_training_labels
                ADD COLUMN release_version TEXT NULL;
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema='public' AND table_name='scan_training_labels' AND column_name='app_version'
        ) THEN
            ALTER TABLE public.scan_training_labels
                ADD COLUMN app_version TEXT NULL;
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema='public' AND table_name='scan_training_labels' AND column_name='taxonomy_version'
        ) THEN
            ALTER TABLE public.scan_training_labels
                ADD COLUMN taxonomy_version TEXT NULL;
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema='public' AND table_name='scan_training_labels' AND column_name='metadata'
        ) THEN
            ALTER TABLE public.scan_training_labels
                ADD COLUMN metadata JSONB NOT NULL DEFAULT '{}'::jsonb;
        END IF;

        CREATE INDEX IF NOT EXISTS idx_scan_training_labels_scan_id
            ON public.scan_training_labels(scan_id, created_at DESC);

        CREATE INDEX IF NOT EXISTS idx_scan_training_labels_item_signature
            ON public.scan_training_labels(item_signature);
    END IF;
END $$;
