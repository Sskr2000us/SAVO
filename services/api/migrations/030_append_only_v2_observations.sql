-- Append-only hardening for V2 observations
-- Date: 2026-01-10
-- Purpose:
--  - Enforce core principle: observations are append-only
--  - Mirror the existing append-only guardrails from 024 onto observations.scan_observations_v2

-- Define the guard function (idempotent). This function is also created in 024,
-- but repeating it here keeps this migration standalone and fixes nested $$ issues.
CREATE OR REPLACE FUNCTION public.prevent_update_delete()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'This table is append-only; updates/deletes are not allowed';
END;
$$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema='observations' AND table_name='scan_observations_v2'
    ) THEN
        IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='scan_observations_v2_prevent_update') THEN
            EXECUTE 'CREATE TRIGGER scan_observations_v2_prevent_update BEFORE UPDATE ON observations.scan_observations_v2 FOR EACH ROW EXECUTE FUNCTION public.prevent_update_delete()';
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='scan_observations_v2_prevent_delete') THEN
            EXECUTE 'CREATE TRIGGER scan_observations_v2_prevent_delete BEFORE DELETE ON observations.scan_observations_v2 FOR EACH ROW EXECUTE FUNCTION public.prevent_update_delete()';
        END IF;
    END IF;
END $$;
