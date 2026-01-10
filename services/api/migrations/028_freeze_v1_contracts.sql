-- Freeze V1 contracts (zero trust stabilization)
--
-- Goal: Make any *_v1 tables immutable (reject INSERT/UPDATE/DELETE)
-- while allowing explicitly-authorized maintenance in a controlled way.
--
-- IMPORTANT:
--  - This migration is safe to apply even if you have no *_v1 tables yet.
--  - This does NOT touch current "live" tables (no renames, no schema changes).
--
-- Allowlist mechanism (for exceptional maintenance / bug-fix migrations):
--  - Wrap your migration in a transaction and set:
--      BEGIN;
--      SET LOCAL savo.allow_v1_writes = 'on';
--      -- your DML here
--      COMMIT;
--
-- If you violate this rule, you risk historical corruption.

DO $savo$
DECLARE
    r record;
BEGIN
    -- 1) Helper: is this session allowed to write to V1?
    IF NOT EXISTS (
        SELECT 1
        FROM pg_proc
        JOIN pg_namespace n ON n.oid = pg_proc.pronamespace
        WHERE n.nspname = 'public' AND pg_proc.proname = 'savo_is_v1_write_allowed'
    ) THEN
        EXECUTE $SQL$
            CREATE FUNCTION public.savo_is_v1_write_allowed()
            RETURNS boolean
            LANGUAGE plpgsql
            AS $fn$
            DECLARE
                allow_setting text;
            BEGIN
                allow_setting := current_setting('savo.allow_v1_writes', true);

                -- Escape hatch for controlled migrations/maintenance only.
                IF allow_setting = 'on' THEN
                    RETURN true;
                END IF;

                -- Postgres/Supabase admins (SQL editor / migrations) typically run as elevated roles.
                -- We keep this list intentionally tight; normal runtime roles should NOT be here.
                IF current_user IN ('postgres', 'supabase_admin') THEN
                    RETURN true;
                END IF;

                RETURN false;
            END;
            $fn$;
        $SQL$;
    END IF;

    -- 2) Trigger function: prevent any write on *_v1 relations.
    IF NOT EXISTS (
        SELECT 1
        FROM pg_proc
        JOIN pg_namespace n ON n.oid = pg_proc.pronamespace
        WHERE n.nspname = 'public' AND pg_proc.proname = 'prevent_v1_writes'
    ) THEN
        EXECUTE $SQL$
            CREATE FUNCTION public.prevent_v1_writes()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $fn$
            BEGIN
                IF public.savo_is_v1_write_allowed() THEN
                    IF TG_OP = 'DELETE' THEN
                        RETURN OLD;
                    END IF;
                    RETURN NEW;
                END IF;

                RAISE EXCEPTION 'V1 contract is frozen: % on %.% is not allowed', TG_OP, TG_TABLE_SCHEMA, TG_TABLE_NAME
                    USING ERRCODE = '42501';
            END;
            $fn$;
        $SQL$;
    END IF;

    -- 3) Attach freeze triggers to every *_v1 table (any schema).
    --    If none exist yet, this is a no-op.
        FOR r IN
                SELECT table_schema, table_name
                FROM information_schema.tables
                WHERE table_type = 'BASE TABLE'
                    AND table_schema NOT IN ('pg_catalog', 'information_schema')
                    AND table_name ~ '_v1$'
    LOOP
        IF NOT EXISTS (
            SELECT 1
            FROM pg_trigger t
            JOIN pg_class c ON c.oid = t.tgrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE t.tgname = 'freeze_v1_' || substr(md5(r.table_schema || '.' || r.table_name), 1, 16)
              AND n.nspname = r.table_schema
              AND c.relname = r.table_name
        ) THEN
            EXECUTE format(
                'CREATE TRIGGER %I BEFORE INSERT OR UPDATE OR DELETE ON %I.%I FOR EACH ROW EXECUTE FUNCTION public.prevent_v1_writes()'
                , 'freeze_v1_' || substr(md5(r.table_schema || '.' || r.table_name), 1, 16), r.table_schema, r.table_name
            );
        END IF;
    END LOOP;

END
$savo$;
