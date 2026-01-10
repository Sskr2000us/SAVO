-- Side-by-side versioned schemas (V1 + V2)
--
-- Principles:
--  - V2 tables are introduced without dropping/replacing existing tables.
--  - V1 remains readable; write path can be configured (app-level feature flags).
--  - V2 tables include required version stamps where applicable:
--      vision_model_version, quantity_model_version, taxonomy_version, embedding_version
--
-- This migration is idempotent.

DO $savo$
BEGIN
    -- ---------------------------------------------------------------------
    -- Pantry truth: inventory_items_v2 (side-by-side)
    -- ---------------------------------------------------------------------
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema='public' AND table_name='inventory_items_v2'
    ) THEN
        -- Copy column structure (no named constraints to avoid collisions).
        EXECUTE 'CREATE TABLE public.inventory_items_v2 (LIKE public.inventory_items INCLUDING DEFAULTS INCLUDING IDENTITY INCLUDING GENERATED)';
    END IF;

    -- Add required version stamps (nullable, app-stamped).
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema='public' AND table_name='inventory_items_v2' AND column_name='vision_model_version'
    ) THEN
        ALTER TABLE public.inventory_items_v2 ADD COLUMN vision_model_version TEXT NULL;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema='public' AND table_name='inventory_items_v2' AND column_name='quantity_model_version'
    ) THEN
        ALTER TABLE public.inventory_items_v2 ADD COLUMN quantity_model_version TEXT NULL;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema='public' AND table_name='inventory_items_v2' AND column_name='taxonomy_version'
    ) THEN
        ALTER TABLE public.inventory_items_v2 ADD COLUMN taxonomy_version TEXT NULL;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema='public' AND table_name='inventory_items_v2' AND column_name='embedding_version'
    ) THEN
        ALTER TABLE public.inventory_items_v2 ADD COLUMN embedding_version TEXT NULL;
    END IF;

    -- Ensure primary key exists on id (LIKE does not include constraints).
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conrelid = 'public.inventory_items_v2'::regclass
          AND contype = 'p'
    ) THEN
        EXECUTE 'ALTER TABLE public.inventory_items_v2 ADD CONSTRAINT inventory_items_v2_pkey PRIMARY KEY (id)';
    END IF;

    -- Enable RLS + policies equivalent to inventory_items.
    BEGIN
        EXECUTE 'ALTER TABLE public.inventory_items_v2 ENABLE ROW LEVEL SECURITY';
    EXCEPTION WHEN OTHERS THEN
        NULL;
    END;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname='public' AND tablename='inventory_items_v2' AND policyname='Users can view own inventory v2'
    ) THEN
        EXECUTE $pol$
            CREATE POLICY "Users can view own inventory v2" ON public.inventory_items_v2
                FOR SELECT USING (auth.uid() = user_id);
        $pol$;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname='public' AND tablename='inventory_items_v2' AND policyname='Users can insert own inventory v2'
    ) THEN
        EXECUTE $pol$
            CREATE POLICY "Users can insert own inventory v2" ON public.inventory_items_v2
                FOR INSERT WITH CHECK (auth.uid() = user_id);
        $pol$;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname='public' AND tablename='inventory_items_v2' AND policyname='Users can update own inventory v2'
    ) THEN
        EXECUTE $pol$
            CREATE POLICY "Users can update own inventory v2" ON public.inventory_items_v2
                FOR UPDATE USING (auth.uid() = user_id);
        $pol$;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname='public' AND tablename='inventory_items_v2' AND policyname='Users can delete own inventory v2'
    ) THEN
        EXECUTE $pol$
            CREATE POLICY "Users can delete own inventory v2" ON public.inventory_items_v2
                FOR DELETE USING (auth.uid() = user_id);
        $pol$;
    END IF;

    -- Reuse low-stock trigger function for parity (best-effort).
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_trigger
            WHERE tgname = 'check_inventory_low_stock_v2'
        ) THEN
            EXECUTE 'CREATE TRIGGER check_inventory_low_stock_v2 BEFORE INSERT OR UPDATE OF quantity, low_stock_threshold ON public.inventory_items_v2 FOR EACH ROW EXECUTE FUNCTION check_low_stock()';
        END IF;
    EXCEPTION WHEN OTHERS THEN
        NULL;
    END;

    -- Versioned stable views (V1 and V2).
    EXECUTE 'CREATE OR REPLACE VIEW public.pantry_items_v1 AS SELECT * FROM public.inventory_items';
    EXECUTE 'CREATE OR REPLACE VIEW public.pantry_items_v2 AS SELECT * FROM public.inventory_items_v2';

    -- ---------------------------------------------------------------------
    -- Observations: scan_observations_v2 (side-by-side)
    -- ---------------------------------------------------------------------
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema='observations' AND table_name='scan_observations_v2'
    ) THEN
        EXECUTE 'CREATE TABLE observations.scan_observations_v2 (LIKE observations.scan_observations INCLUDING DEFAULTS INCLUDING IDENTITY INCLUDING GENERATED)';
    END IF;

    -- Required version stamps (taxonomy_version exists in v1 after 027; keep explicit for v2).
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema='observations' AND table_name='scan_observations_v2' AND column_name='vision_model_version'
    ) THEN
        ALTER TABLE observations.scan_observations_v2 ADD COLUMN vision_model_version TEXT NULL;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema='observations' AND table_name='scan_observations_v2' AND column_name='quantity_model_version'
    ) THEN
        ALTER TABLE observations.scan_observations_v2 ADD COLUMN quantity_model_version TEXT NULL;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema='observations' AND table_name='scan_observations_v2' AND column_name='taxonomy_version'
    ) THEN
        ALTER TABLE observations.scan_observations_v2 ADD COLUMN taxonomy_version TEXT NULL;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema='observations' AND table_name='scan_observations_v2' AND column_name='embedding_version'
    ) THEN
        ALTER TABLE observations.scan_observations_v2 ADD COLUMN embedding_version TEXT NULL;
    END IF;

    -- Ensure primary key exists on id.
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conrelid = 'observations.scan_observations_v2'::regclass
          AND contype = 'p'
    ) THEN
        EXECUTE 'ALTER TABLE observations.scan_observations_v2 ADD CONSTRAINT scan_observations_v2_pkey PRIMARY KEY (id)';
    END IF;

    -- RLS + policies analogous to scan_observations.
    BEGIN
        EXECUTE 'ALTER TABLE observations.scan_observations_v2 ENABLE ROW LEVEL SECURITY';
    EXCEPTION WHEN OTHERS THEN
        NULL;
    END;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname='observations' AND tablename='scan_observations_v2' AND policyname='Users can view their own scan observations v2'
    ) THEN
        EXECUTE $pol$
            CREATE POLICY "Users can view their own scan observations v2"
                ON observations.scan_observations_v2 FOR SELECT
                USING (auth.uid() = user_id);
        $pol$;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname='observations' AND tablename='scan_observations_v2' AND policyname='Users can insert their own scan observations v2'
    ) THEN
        EXECUTE $pol$
            CREATE POLICY "Users can insert their own scan observations v2"
                ON observations.scan_observations_v2 FOR INSERT
                WITH CHECK (auth.uid() = user_id);
        $pol$;
    END IF;

    -- Stable public views for PostgREST access.
    BEGIN
        EXECUTE 'DROP VIEW IF EXISTS public.scan_observations_v1';
        EXECUTE 'CREATE VIEW public.scan_observations_v1 WITH (security_invoker=true) AS SELECT * FROM observations.scan_observations';
    EXCEPTION WHEN OTHERS THEN
        EXECUTE 'DROP VIEW IF EXISTS public.scan_observations_v1';
        EXECUTE 'CREATE VIEW public.scan_observations_v1 AS SELECT * FROM observations.scan_observations';
    END;

    BEGIN
        EXECUTE 'DROP VIEW IF EXISTS public.scan_observations_v2';
        EXECUTE 'CREATE VIEW public.scan_observations_v2 WITH (security_invoker=true) AS SELECT * FROM observations.scan_observations_v2';
    EXCEPTION WHEN OTHERS THEN
        EXECUTE 'DROP VIEW IF EXISTS public.scan_observations_v2';
        EXECUTE 'CREATE VIEW public.scan_observations_v2 AS SELECT * FROM observations.scan_observations_v2';
    END;

END
$savo$;
