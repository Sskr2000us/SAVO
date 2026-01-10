-- Decision required versions enforcement
-- Date: 2026-01-10
-- Purpose:
--  - Ensure ingredient_actions (decisions) are stamped with required versions
--  - Reject inserts missing required versions (additive via trigger)

DO $do$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema='public' AND table_name='ingredient_actions'
    ) THEN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema='public' AND table_name='ingredient_actions' AND column_name='vision_model_version'
        ) THEN
            ALTER TABLE public.ingredient_actions ADD COLUMN vision_model_version TEXT NULL;
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema='public' AND table_name='ingredient_actions' AND column_name='quantity_model_version'
        ) THEN
            ALTER TABLE public.ingredient_actions ADD COLUMN quantity_model_version TEXT NULL;
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema='public' AND table_name='ingredient_actions' AND column_name='taxonomy_version'
        ) THEN
            ALTER TABLE public.ingredient_actions ADD COLUMN taxonomy_version TEXT NULL;
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema='public' AND table_name='ingredient_actions' AND column_name='embedding_version'
        ) THEN
            ALTER TABLE public.ingredient_actions ADD COLUMN embedding_version TEXT NULL;
        END IF;

        EXECUTE $fn$
            CREATE OR REPLACE FUNCTION public.enforce_required_versions_ingredient_actions()
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
                    RAISE EXCEPTION 'required_versions_check: ingredient_actions missing one or more required versions'
                        USING ERRCODE = '23514';
                END IF;

                RETURN NEW;
            END;
            $$;
        $fn$;

        IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='ingredient_actions_required_versions') THEN
            EXECUTE 'CREATE TRIGGER ingredient_actions_required_versions BEFORE INSERT ON public.ingredient_actions FOR EACH ROW EXECUTE FUNCTION public.enforce_required_versions_ingredient_actions()';
        END IF;
    END IF;
END $do$;
