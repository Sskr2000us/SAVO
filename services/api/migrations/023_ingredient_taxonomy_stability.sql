-- Ingredient Taxonomy Stability + Relationships
-- Date: 2026-01-10
-- Purpose:
--  - Stable canonical IDs across taxonomy upgrades (deprecation + redirect)
--  - Prevent hard-deletes of master ingredients (use status=deprecated)
--  - Add derived-from relationships
--  - Link pantry truth items to master ingredient IDs

-- ============================================================================
-- 1. master_ingredients: deprecation + redirect metadata
-- ============================================================================

DO $$
BEGIN
    ALTER TABLE public.master_ingredients ADD COLUMN IF NOT EXISTS replaced_by_id UUID;
    ALTER TABLE public.master_ingredients ADD COLUMN IF NOT EXISTS deprecated_at TIMESTAMPTZ;
    ALTER TABLE public.master_ingredients ADD COLUMN IF NOT EXISTS deprecation_reason TEXT;
END $$;

DO $$
BEGIN
    -- Foreign key to allow redirect chains while preventing deletion of replacement target.
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'master_ingredients_replaced_by_fkey'
    ) THEN
        ALTER TABLE public.master_ingredients
        ADD CONSTRAINT master_ingredients_replaced_by_fkey
        FOREIGN KEY (replaced_by_id) REFERENCES public.master_ingredients(id) ON DELETE RESTRICT;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'check_master_ingredients_replaced_by'
    ) THEN
        ALTER TABLE public.master_ingredients
        ADD CONSTRAINT check_master_ingredients_replaced_by
        CHECK (replaced_by_id IS NULL OR replaced_by_id <> id);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_master_ingredients_replaced_by_id ON public.master_ingredients(replaced_by_id);
CREATE INDEX IF NOT EXISTS idx_master_ingredients_deprecated_at ON public.master_ingredients(deprecated_at);

-- Resolve stable ingredient ID by following replaced_by_id (up to 20 hops)
DROP FUNCTION IF EXISTS public.resolve_master_ingredient_id(UUID);
CREATE OR REPLACE FUNCTION public.resolve_master_ingredient_id(p_id UUID)
RETURNS UUID
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    current_id UUID := p_id;
    next_id UUID;
    depth INT := 0;
BEGIN
    WHILE current_id IS NOT NULL LOOP
        SELECT replaced_by_id INTO next_id
        FROM public.master_ingredients
        WHERE id = current_id;

        IF next_id IS NULL THEN
            RETURN current_id;
        END IF;

        current_id := next_id;
        depth := depth + 1;
        IF depth > 20 THEN
            RETURN current_id;
        END IF;
    END LOOP;

    RETURN p_id;
END;
$$;

COMMENT ON FUNCTION public.resolve_master_ingredient_id IS 'Follows master_ingredients.replaced_by_id to return current canonical ID';

-- Prevent hard-delete of master_ingredients; require deprecation instead.
DROP FUNCTION IF EXISTS public.prevent_master_ingredients_delete();
CREATE OR REPLACE FUNCTION public.prevent_master_ingredients_delete()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'master_ingredients rows must be deprecated, not deleted';
END;
$$;

DROP TRIGGER IF EXISTS prevent_master_ingredients_delete_trigger ON public.master_ingredients;
CREATE TRIGGER prevent_master_ingredients_delete_trigger
BEFORE DELETE ON public.master_ingredients
FOR EACH ROW
EXECUTE FUNCTION public.prevent_master_ingredients_delete();

-- ============================================================================
-- 2. Pantry truth: link inventory_items -> master_ingredients
-- ============================================================================

DO $$
BEGIN
    ALTER TABLE public.inventory_items ADD COLUMN IF NOT EXISTS ingredient_id UUID;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'inventory_items_ingredient_id_fkey'
    ) THEN
        ALTER TABLE public.inventory_items
        ADD CONSTRAINT inventory_items_ingredient_id_fkey
        FOREIGN KEY (ingredient_id) REFERENCES public.master_ingredients(id) ON DELETE SET NULL;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_inventory_items_ingredient_id ON public.inventory_items(ingredient_id);

-- Best-effort backfill from canonical_name and aliases.
UPDATE public.inventory_items ii
SET ingredient_id = mi.id
FROM public.master_ingredients mi
WHERE ii.ingredient_id IS NULL
  AND lower(ii.canonical_name) = lower(mi.canonical_name);

UPDATE public.inventory_items ii
SET ingredient_id = ia.ingredient_id
FROM public.ingredient_aliases ia
WHERE ii.ingredient_id IS NULL
  AND lower(ii.canonical_name) = lower(ia.alias_name);

-- ============================================================================
-- 3. Derived relationships
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.ingredient_derivations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Example: base=milk, derived=cheese; base=grape, derived=raisins
    base_ingredient_id UUID NOT NULL REFERENCES public.master_ingredients(id) ON DELETE CASCADE,
    derived_ingredient_id UUID NOT NULL REFERENCES public.master_ingredients(id) ON DELETE CASCADE,

    derivation_type TEXT NOT NULL DEFAULT 'derived_from',
    confidence NUMERIC(3,2) DEFAULT 1.00 CHECK (confidence >= 0 AND confidence <= 1),

    cuisine_types TEXT[],
    notes TEXT,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT unique_derivation UNIQUE(base_ingredient_id, derived_ingredient_id, derivation_type),
    CONSTRAINT different_ingredients_derivation CHECK (base_ingredient_id <> derived_ingredient_id)
);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'check_derivation_type'
    ) THEN
        ALTER TABLE public.ingredient_derivations
        ADD CONSTRAINT check_derivation_type
        CHECK (derivation_type IN ('derived_from', 'made_from', 'variety_of', 'processed_from'));
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_derivations_base ON public.ingredient_derivations(base_ingredient_id);
CREATE INDEX IF NOT EXISTS idx_derivations_derived ON public.ingredient_derivations(derived_ingredient_id);
CREATE INDEX IF NOT EXISTS idx_derivations_type ON public.ingredient_derivations(derivation_type);

COMMENT ON TABLE public.ingredient_derivations IS 'Directed graph of derived-from relationships (base -> derived)';

ALTER TABLE public.ingredient_derivations ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS ingredient_derivations_read_policy ON public.ingredient_derivations;
CREATE POLICY ingredient_derivations_read_policy ON public.ingredient_derivations
    FOR SELECT USING (true);

DROP POLICY IF EXISTS ingredient_derivations_write_policy ON public.ingredient_derivations;
CREATE POLICY ingredient_derivations_write_policy ON public.ingredient_derivations
    FOR ALL USING (auth.uid() IS NOT NULL);
