-- Pantry truth fields + auditable AI observations schema
-- Date: 2026-01-09

DO $$
BEGIN
    -- ---------------------------------------------------------------------
    -- Inventory items: add explicit pantry truth fields
    -- ---------------------------------------------------------------------
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema='public' AND table_name='inventory_items'
    ) THEN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema='public' AND table_name='inventory_items' AND column_name='pantry_status'
        ) THEN
            ALTER TABLE public.inventory_items
                ADD COLUMN pantry_status TEXT NOT NULL DEFAULT 'active'
                CHECK (pantry_status IN ('active', 'consumed', 'discarded'));
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema='public' AND table_name='inventory_items' AND column_name='last_confirmed_at'
        ) THEN
            ALTER TABLE public.inventory_items
                ADD COLUMN last_confirmed_at TIMESTAMPTZ NULL;
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema='public' AND table_name='inventory_items' AND column_name='last_status_changed_at'
        ) THEN
            ALTER TABLE public.inventory_items
                ADD COLUMN last_status_changed_at TIMESTAMPTZ NULL;
        END IF;

        CREATE INDEX IF NOT EXISTS idx_inventory_items_user_pantry_status
            ON public.inventory_items(user_id, pantry_status, updated_at DESC);

        CREATE INDEX IF NOT EXISTS idx_inventory_items_user_last_confirmed
            ON public.inventory_items(user_id, last_confirmed_at DESC);
    END IF;

    -- ---------------------------------------------------------------------
    -- Public naming: pantry_items view as a stable alias over inventory_items
    -- (keeps inventory_items as the physical truth table for backward compat)
    -- ---------------------------------------------------------------------
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.views
        WHERE table_schema='public' AND table_name='pantry_items'
    ) THEN
        EXECUTE $sql$
            CREATE VIEW public.pantry_items AS
            SELECT *
            FROM public.inventory_items
        $sql$;
    END IF;

    -- ---------------------------------------------------------------------
    -- Observations schema: auditable inference outputs (no raw frames)
    -- ---------------------------------------------------------------------
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.schemata
        WHERE schema_name = 'observations'
    ) THEN
        EXECUTE 'CREATE SCHEMA observations';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema='observations' AND table_name='scan_observations'
    ) THEN
        EXECUTE $sql$
            CREATE TABLE observations.scan_observations (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                observed_at TIMESTAMPTZ NOT NULL DEFAULT now(),

                user_id UUID NOT NULL,
                scan_id UUID NULL REFERENCES public.ingredient_scans(id) ON DELETE SET NULL,
                session_id UUID NULL,
                correlation_id UUID NULL,

                source TEXT NOT NULL CHECK (source IN ('image', 'frames', 'barcode')),
                storage_location TEXT NULL CHECK (storage_location IN ('pantry', 'fridge', 'freezer', 'counter')),

                observed_entity_type TEXT NOT NULL DEFAULT 'ingredient',
                observed_entity_id UUID NULL,

                detected_name TEXT NULL,
                canonical_name TEXT NULL,
                confidence DECIMAL(3,2) NULL CHECK (confidence BETWEEN 0 AND 1),

                quantity DECIMAL(10,2) NULL,
                unit TEXT NULL,

                bbox JSONB NULL,
                metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                raw JSONB NOT NULL DEFAULT '{}'::jsonb,

                model_provider TEXT NULL,
                model_version TEXT NULL,
                release_version TEXT NULL,
                app_version TEXT NULL
            );
        $sql$;

        EXECUTE 'CREATE INDEX scan_observations_user_ts_idx ON observations.scan_observations(user_id, observed_at DESC)';
        EXECUTE 'CREATE INDEX scan_observations_scan_ts_idx ON observations.scan_observations(scan_id, observed_at DESC)';
        EXECUTE 'CREATE INDEX scan_observations_session_ts_idx ON observations.scan_observations(session_id, observed_at DESC)';

        EXECUTE 'ALTER TABLE observations.scan_observations ENABLE ROW LEVEL SECURITY';

        IF NOT EXISTS (
            SELECT 1 FROM pg_policies
            WHERE schemaname='observations' AND tablename='scan_observations' AND policyname='Users can view their own scan observations'
        ) THEN
            EXECUTE $sql$
                CREATE POLICY "Users can view their own scan observations"
                    ON observations.scan_observations FOR SELECT
                    USING (auth.uid() = user_id)
            $sql$;
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM pg_policies
            WHERE schemaname='observations' AND tablename='scan_observations' AND policyname='Users can insert their own scan observations'
        ) THEN
            EXECUTE $sql$
                CREATE POLICY "Users can insert their own scan observations"
                    ON observations.scan_observations FOR INSERT
                    WITH CHECK (auth.uid() = user_id)
            $sql$;
        END IF;
    END IF;

    -- Expose a stable public view for API access.
    -- PostgREST/Supabase commonly exposes only the public schema unless configured.
    BEGIN
        EXECUTE 'DROP VIEW IF EXISTS public.scan_observations';
        EXECUTE 'CREATE VIEW public.scan_observations WITH (security_invoker=true) AS SELECT * FROM observations.scan_observations';
    EXCEPTION WHEN OTHERS THEN
        -- If security_invoker is unsupported (older PG), fall back to a plain view.
        BEGIN
            EXECUTE 'DROP VIEW IF EXISTS public.scan_observations';
            EXECUTE 'CREATE VIEW public.scan_observations AS SELECT * FROM observations.scan_observations';
        EXCEPTION WHEN OTHERS THEN
            NULL;
        END;
    END;
END $$;
