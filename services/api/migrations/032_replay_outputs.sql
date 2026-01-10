-- Replay outputs: append-only run records + pantry snapshots
-- Date: 2026-01-10
-- Purpose:
--  - Support deterministic replay without rewriting truth tables
--  - Store replay outputs append-only for audit and debugging

DO $$
BEGIN
    -- ---------------------------------------------------------------------
    -- replay_runs
    -- ---------------------------------------------------------------------
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema='public' AND table_name='replay_runs'
    ) THEN
        EXECUTE $sql$
            CREATE TABLE public.replay_runs (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

                user_id UUID NULL,
                from_ts TIMESTAMPTZ NULL,
                to_ts TIMESTAMPTZ NULL,

                interpreter_version TEXT NOT NULL,
                metadata JSONB NOT NULL DEFAULT '{}'::jsonb
            );
        $sql$;

        EXECUTE 'CREATE INDEX replay_runs_user_created_idx ON public.replay_runs(user_id, created_at DESC)';
        EXECUTE 'ALTER TABLE public.replay_runs ENABLE ROW LEVEL SECURITY';

        DROP POLICY IF EXISTS replay_runs_read_own ON public.replay_runs;
        EXECUTE 'CREATE POLICY replay_runs_read_own ON public.replay_runs FOR SELECT USING (auth.uid() = user_id)';

        DROP POLICY IF EXISTS replay_runs_insert_own ON public.replay_runs;
        EXECUTE 'CREATE POLICY replay_runs_insert_own ON public.replay_runs FOR INSERT WITH CHECK (auth.uid() = user_id)';
    END IF;

    -- ---------------------------------------------------------------------
    -- replay_inventory_snapshots
    -- ---------------------------------------------------------------------
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema='public' AND table_name='replay_inventory_snapshots'
    ) THEN
        EXECUTE $sql$
            CREATE TABLE public.replay_inventory_snapshots (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

                run_id UUID NOT NULL REFERENCES public.replay_runs(id) ON DELETE RESTRICT,
                user_id UUID NULL,

                inventory_item_id UUID NULL,
                canonical_name TEXT NULL,
                storage_location TEXT NULL,
                item_state TEXT NULL,

                snapshot JSONB NOT NULL DEFAULT '{}'::jsonb
            );
        $sql$;

        EXECUTE 'CREATE INDEX replay_inventory_snapshots_run_idx ON public.replay_inventory_snapshots(run_id, created_at DESC)';
        EXECUTE 'CREATE INDEX replay_inventory_snapshots_user_created_idx ON public.replay_inventory_snapshots(user_id, created_at DESC)';
        EXECUTE 'ALTER TABLE public.replay_inventory_snapshots ENABLE ROW LEVEL SECURITY';

        DROP POLICY IF EXISTS replay_inventory_snapshots_read_own ON public.replay_inventory_snapshots;
        EXECUTE 'CREATE POLICY replay_inventory_snapshots_read_own ON public.replay_inventory_snapshots FOR SELECT USING (auth.uid() = user_id)';

        DROP POLICY IF EXISTS replay_inventory_snapshots_insert_own ON public.replay_inventory_snapshots;
        EXECUTE 'CREATE POLICY replay_inventory_snapshots_insert_own ON public.replay_inventory_snapshots FOR INSERT WITH CHECK (auth.uid() = user_id)';
    END IF;

    -- ---------------------------------------------------------------------
    -- Append-only hardening for replay outputs
    -- ---------------------------------------------------------------------
    IF EXISTS (
        SELECT 1 FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'public' AND p.proname = 'prevent_update_delete'
    ) THEN
        IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='replay_runs_prevent_update') THEN
            EXECUTE 'CREATE TRIGGER replay_runs_prevent_update BEFORE UPDATE ON public.replay_runs FOR EACH ROW EXECUTE FUNCTION public.prevent_update_delete()';
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='replay_runs_prevent_delete') THEN
            EXECUTE 'CREATE TRIGGER replay_runs_prevent_delete BEFORE DELETE ON public.replay_runs FOR EACH ROW EXECUTE FUNCTION public.prevent_update_delete()';
        END IF;

        IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='replay_inventory_snapshots_prevent_update') THEN
            EXECUTE 'CREATE TRIGGER replay_inventory_snapshots_prevent_update BEFORE UPDATE ON public.replay_inventory_snapshots FOR EACH ROW EXECUTE FUNCTION public.prevent_update_delete()';
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='replay_inventory_snapshots_prevent_delete') THEN
            EXECUTE 'CREATE TRIGGER replay_inventory_snapshots_prevent_delete BEFORE DELETE ON public.replay_inventory_snapshots FOR EACH ROW EXECUTE FUNCTION public.prevent_update_delete()';
        END IF;
    END IF;
END $$;
