-- Fix auto_add_to_pantry to be compatible across DB schemas
--
-- Problem:
-- Some deployments have an older trigger/function that tries to insert `scan_id`
-- into `public.user_pantry`, but the table schema uses `source_scan_id` instead.
-- This breaks confirmations with:
--   column "scan_id" of relation "user_pantry" does not exist (42703)
--
-- This migration replaces the trigger function with a version that dynamically
-- targets whichever columns exist (`source_scan_id` preferred, `scan_id` legacy),
-- so the confirm flow can always write inventory.

CREATE OR REPLACE FUNCTION public.auto_add_to_pantry()
RETURNS TRIGGER AS $$
DECLARE
  has_source_scan_id BOOLEAN;
  has_scan_id BOOLEAN;
  has_source_detected_id BOOLEAN;
  has_detected_id BOOLEAN;
  col_scan TEXT;
  col_detected TEXT;
  sql TEXT;
BEGIN
  IF NEW.confirmation_status = 'confirmed' AND NEW.confirmed_name IS NOT NULL THEN
    SELECT EXISTS(
      SELECT 1
      FROM information_schema.columns
      WHERE table_schema = 'public'
        AND table_name = 'user_pantry'
        AND column_name = 'source_scan_id'
    ) INTO has_source_scan_id;

    SELECT EXISTS(
      SELECT 1
      FROM information_schema.columns
      WHERE table_schema = 'public'
        AND table_name = 'user_pantry'
        AND column_name = 'scan_id'
    ) INTO has_scan_id;

    SELECT EXISTS(
      SELECT 1
      FROM information_schema.columns
      WHERE table_schema = 'public'
        AND table_name = 'user_pantry'
        AND column_name = 'source_detected_id'
    ) INTO has_source_detected_id;

    SELECT EXISTS(
      SELECT 1
      FROM information_schema.columns
      WHERE table_schema = 'public'
        AND table_name = 'user_pantry'
        AND column_name = 'detected_id'
    ) INTO has_detected_id;

    col_scan := NULL;
    IF has_source_scan_id THEN
      col_scan := 'source_scan_id';
    ELSIF has_scan_id THEN
      col_scan := 'scan_id';
    END IF;

    col_detected := NULL;
    IF has_source_detected_id THEN
      col_detected := 'source_detected_id';
    ELSIF has_detected_id THEN
      col_detected := 'detected_id';
    END IF;

    sql := 'INSERT INTO public.user_pantry (user_id, ingredient_name, display_name, source, status';
    IF col_scan IS NOT NULL THEN
      sql := sql || ', ' || col_scan;
    END IF;
    IF col_detected IS NOT NULL THEN
      sql := sql || ', ' || col_detected;
    END IF;

    sql := sql || ') VALUES ($1, LOWER($2), $2, ''scan'', ''available''';

    IF col_scan IS NOT NULL AND col_detected IS NOT NULL THEN
      sql := sql || ', $3, $4)';
      sql := sql || ' ON CONFLICT (user_id, ingredient_name) DO UPDATE SET status=''available'', added_at=NOW(), removed_at=NULL;';
      EXECUTE sql USING NEW.user_id, NEW.confirmed_name, NEW.scan_id, NEW.id;
    ELSIF col_scan IS NOT NULL AND col_detected IS NULL THEN
      sql := sql || ', $3)';
      sql := sql || ' ON CONFLICT (user_id, ingredient_name) DO UPDATE SET status=''available'', added_at=NOW(), removed_at=NULL;';
      EXECUTE sql USING NEW.user_id, NEW.confirmed_name, NEW.scan_id;
    ELSIF col_scan IS NULL AND col_detected IS NOT NULL THEN
      sql := sql || ', $3)';
      sql := sql || ' ON CONFLICT (user_id, ingredient_name) DO UPDATE SET status=''available'', added_at=NOW(), removed_at=NULL;';
      EXECUTE sql USING NEW.user_id, NEW.confirmed_name, NEW.id;
    ELSE
      sql := sql || ')';
      sql := sql || ' ON CONFLICT (user_id, ingredient_name) DO UPDATE SET status=''available'', added_at=NOW(), removed_at=NULL;';
      EXECUTE sql USING NEW.user_id, NEW.confirmed_name;
    END IF;
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
BEGIN
  -- Re-point the trigger to the updated function (safe to re-run)
  DROP TRIGGER IF EXISTS trigger_auto_add_to_pantry ON public.detected_ingredients;
  CREATE TRIGGER trigger_auto_add_to_pantry
    AFTER UPDATE ON public.detected_ingredients
    FOR EACH ROW
    WHEN (OLD.confirmation_status IS DISTINCT FROM NEW.confirmation_status)
    EXECUTE FUNCTION public.auto_add_to_pantry();
END $$;
