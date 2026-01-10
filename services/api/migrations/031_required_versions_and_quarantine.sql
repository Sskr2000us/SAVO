-- Required version enforcement + quarantine for inference outputs
-- Date: 2026-01-10
-- Purpose:
--  - Ensure observations/decisions are scientifically valid by stamping required versions
--  - Reject inference rows missing required versions, and provide a quarantine sink
--  - Keep changes additive/backward compatible

DO $do$
BEGIN
    -- ---------------------------------------------------------------------
    -- Quarantine table (observations schema)
    -- ---------------------------------------------------------------------
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.schemata
        WHERE schema_name = 'observations'
    ) THEN
        EXECUTE 'CREATE SCHEMA observations';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema='observations' AND table_name='inference_quarantine'
    ) THEN
        EXECUTE $sql$
            CREATE TABLE observations.inference_quarantine (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                quarantined_at TIMESTAMPTZ NOT NULL DEFAULT now(),

                user_id UUID NULL,
                source_table TEXT NOT NULL,
                reason TEXT NOT NULL,

                row_data JSONB NOT NULL DEFAULT '{}'::jsonb,
                metadata JSONB NOT NULL DEFAULT '{}'::jsonb
            );
        $sql$;

        EXECUTE 'CREATE INDEX inference_quarantine_ts_idx ON observations.inference_quarantine(quarantined_at DESC)';
        EXECUTE 'CREATE INDEX inference_quarantine_user_ts_idx ON observations.inference_quarantine(user_id, quarantined_at DESC)';

        EXECUTE 'ALTER TABLE observations.inference_quarantine ENABLE ROW LEVEL SECURITY';

        -- Users can insert quarantine records for themselves (best-effort safety net).
        IF NOT EXISTS (
            SELECT 1 FROM pg_policies
            WHERE schemaname='observations' AND tablename='inference_quarantine' AND policyname='Users can insert their own inference quarantine'
        ) THEN
            EXECUTE $pol$
                CREATE POLICY "Users can insert their own inference quarantine"
                    ON observations.inference_quarantine FOR INSERT
                    WITH CHECK (auth.uid() = user_id);
            $pol$;
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM pg_policies
            WHERE schemaname='observations' AND tablename='inference_quarantine' AND policyname='Users can view their own inference quarantine'
        ) THEN
            EXECUTE $pol$
                CREATE POLICY "Users can view their own inference quarantine"
                    ON observations.inference_quarantine FOR SELECT
                    USING (auth.uid() = user_id);
            $pol$;
        END IF;
    END IF;

    -- Expose stable public view for PostgREST access.
    BEGIN
        EXECUTE 'DROP VIEW IF EXISTS public.inference_quarantine';
        EXECUTE 'CREATE VIEW public.inference_quarantine WITH (security_invoker=true) AS SELECT * FROM observations.inference_quarantine';
    EXCEPTION WHEN OTHERS THEN
        BEGIN
            EXECUTE 'DROP VIEW IF EXISTS public.inference_quarantine';
            EXECUTE 'CREATE VIEW public.inference_quarantine AS SELECT * FROM observations.inference_quarantine';
        EXCEPTION WHEN OTHERS THEN
            NULL;
        END;
    END;

    -- ---------------------------------------------------------------------
    -- Required versions enforcement (scan_observations_v2)
    -- ---------------------------------------------------------------------
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema='observations' AND table_name='scan_observations_v2'
    ) THEN
        -- Ensure columns exist (defense-in-depth; 029 adds these).
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

        -- Trigger-based enforcement keeps this additive (no NOT NULL required).
        -- We raise 23514 (check_violation) so the application can detect + quarantine.
        EXECUTE $fn$
            CREATE OR REPLACE FUNCTION observations.enforce_required_versions_scan_observations_v2()
            RETURNS TRIGGER
            LANGUAGE plpgsql
            AS $$
            DECLARE
                v_tax TEXT;
                v_vision TEXT;
                v_qty TEXT;
                v_emb TEXT;
            BEGIN
                v_tax := NULLIF(BTRIM(COALESCE(NEW.taxonomy_version, '')), '');
                v_vision := NULLIF(BTRIM(COALESCE(NEW.vision_model_version, '')), '');
                v_qty := NULLIF(BTRIM(COALESCE(NEW.quantity_model_version, '')), '');
                v_emb := NULLIF(BTRIM(COALESCE(NEW.embedding_version, '')), '');

                IF v_tax IS NULL OR v_vision IS NULL OR v_qty IS NULL OR v_emb IS NULL THEN
                    RAISE EXCEPTION 'required_versions_check: missing one or more required versions'
                        USING ERRCODE = '23514';
                END IF;

                RETURN NEW;
            END;
            $$;
        $fn$;

        IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='scan_observations_v2_required_versions') THEN
            EXECUTE 'CREATE TRIGGER scan_observations_v2_required_versions BEFORE INSERT ON observations.scan_observations_v2 FOR EACH ROW EXECUTE FUNCTION observations.enforce_required_versions_scan_observations_v2()';
        END IF;
    END IF;
END $do$;
