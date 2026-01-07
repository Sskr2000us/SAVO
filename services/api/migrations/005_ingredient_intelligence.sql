-- Ingredient Intelligence System - Advanced Features
-- Date: 2026-01-06
-- Purpose: Visual-first ingredient identification, multi-language search, substitution graph, and learning system
-- Prerequisites: Migration 004 (master_ingredients, product_barcodes, etc.)

-- ============================================================================
-- 1. Extend master_ingredients with Intelligence Fields
-- ============================================================================

-- Add intelligence columns to existing master_ingredients table
DO $$
BEGIN
    -- Type and classification
    ALTER TABLE public.master_ingredients ADD COLUMN IF NOT EXISTS ingredient_type TEXT DEFAULT 'single_ingredient';
    ALTER TABLE public.master_ingredients ADD COLUMN IF NOT EXISTS scientific_name TEXT;
    ALTER TABLE public.master_ingredients ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'active';
    
    -- Visual intelligence (for computer vision)
    ALTER TABLE public.master_ingredients ADD COLUMN IF NOT EXISTS visual_states TEXT[];
    ALTER TABLE public.master_ingredients ADD COLUMN IF NOT EXISTS dominant_colors TEXT[];
    ALTER TABLE public.master_ingredients ADD COLUMN IF NOT EXISTS shape_features TEXT[];
    ALTER TABLE public.master_ingredients ADD COLUMN IF NOT EXISTS surface_texture TEXT[];
    
    -- Sensory profile (for detailed matching)
    ALTER TABLE public.master_ingredients ADD COLUMN IF NOT EXISTS taste_profile TEXT[];
    ALTER TABLE public.master_ingredients ADD COLUMN IF NOT EXISTS aroma_profile TEXT[];
    ALTER TABLE public.master_ingredients ADD COLUMN IF NOT EXISTS mouthfeel TEXT[];
    ALTER TABLE public.master_ingredients ADD COLUMN IF NOT EXISTS intensity_level TEXT;
    ALTER TABLE public.master_ingredients ADD COLUMN IF NOT EXISTS heat_level TEXT;
    
    -- Culinary intelligence
    ALTER TABLE public.master_ingredients ADD COLUMN IF NOT EXISTS common_uses TEXT[];
    ALTER TABLE public.master_ingredients ADD COLUMN IF NOT EXISTS cooking_methods TEXT[];
    
    -- Storage and waste prevention
    ALTER TABLE public.master_ingredients ADD COLUMN IF NOT EXISTS storage_conditions JSONB;
    ALTER TABLE public.master_ingredients ADD COLUMN IF NOT EXISTS shelf_life_days JSONB;
    ALTER TABLE public.master_ingredients ADD COLUMN IF NOT EXISTS waste_risk_level TEXT;
    ALTER TABLE public.master_ingredients ADD COLUMN IF NOT EXISTS spoilage_signs TEXT[];
    
    -- AI training metadata
    ALTER TABLE public.master_ingredients ADD COLUMN IF NOT EXISTS cv_labels TEXT[];
    ALTER TABLE public.master_ingredients ADD COLUMN IF NOT EXISTS embedding_tags TEXT[];
    ALTER TABLE public.master_ingredients ADD COLUMN IF NOT EXISTS llm_prompt_hints TEXT[];
    ALTER TABLE public.master_ingredients ADD COLUMN IF NOT EXISTS confidence_threshold NUMERIC(3,2) DEFAULT 0.85;
END $$;

-- Add check constraints
DO $$
BEGIN
    -- Check constraint for ingredient_type
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'check_ingredient_type'
    ) THEN
        ALTER TABLE public.master_ingredients
        ADD CONSTRAINT check_ingredient_type 
        CHECK (ingredient_type IN ('single_ingredient', 'blend', 'composite', 'processed'));
    END IF;
    
    -- Check constraint for status
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'check_status'
    ) THEN
        ALTER TABLE public.master_ingredients
        ADD CONSTRAINT check_status 
        CHECK (status IN ('active', 'deprecated', 'seasonal', 'regional'));
    END IF;
    
    -- Check constraint for waste_risk_level
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'check_waste_risk'
    ) THEN
        ALTER TABLE public.master_ingredients
        ADD CONSTRAINT check_waste_risk 
        CHECK (waste_risk_level IS NULL OR waste_risk_level IN ('low', 'medium', 'high', 'critical'));
    END IF;
    
    -- Check constraint for confidence_threshold
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'check_confidence_threshold'
    ) THEN
        ALTER TABLE public.master_ingredients
        ADD CONSTRAINT check_confidence_threshold 
        CHECK (confidence_threshold IS NULL OR (confidence_threshold >= 0 AND confidence_threshold <= 1));
    END IF;
END $$;

-- Add indexes for new intelligence fields
CREATE INDEX IF NOT EXISTS idx_master_ingredients_type ON public.master_ingredients(ingredient_type);
CREATE INDEX IF NOT EXISTS idx_master_ingredients_status ON public.master_ingredients(status);
CREATE INDEX IF NOT EXISTS idx_master_ingredients_visual_states ON public.master_ingredients USING gin(visual_states);
CREATE INDEX IF NOT EXISTS idx_master_ingredients_cv_labels ON public.master_ingredients USING gin(cv_labels);

COMMENT ON COLUMN public.master_ingredients.ingredient_type IS 'Classification: single_ingredient, blend, composite, processed';
COMMENT ON COLUMN public.master_ingredients.visual_states IS 'Array of visual forms: raw_whole, raw_cut, powdered, cooked';
COMMENT ON COLUMN public.master_ingredients.storage_conditions IS 'Storage requirements by form: {fresh: cool_dry_place, powder: airtight_container}';
COMMENT ON COLUMN public.master_ingredients.shelf_life_days IS 'Expected shelf life by form: {fresh: 30, powder: 180}';
COMMENT ON COLUMN public.master_ingredients.confidence_threshold IS 'Minimum confidence score for AI identification (0.0-1.0)';

-- ============================================================================
-- 2. Ingredient Aliases (Multi-Language Support)
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.ingredient_aliases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ingredient_id UUID NOT NULL REFERENCES public.master_ingredients(id) ON DELETE CASCADE,
    
    -- Alias details
    alias_name TEXT NOT NULL,
    language_code TEXT NOT NULL, -- hi-IN, ta-IN, es-ES, zh-CN, ar-SA
    region TEXT, -- India, Mexico, Thailand
    
    -- Priority and usage
    is_primary BOOLEAN DEFAULT false, -- Is this the primary name for this language?
    usage_frequency INTEGER DEFAULT 0, -- How often users search this term
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT unique_ingredient_alias UNIQUE(ingredient_id, alias_name, language_code)
);

CREATE INDEX IF NOT EXISTS idx_aliases_ingredient ON public.ingredient_aliases(ingredient_id);
CREATE INDEX IF NOT EXISTS idx_aliases_name ON public.ingredient_aliases(alias_name);
CREATE INDEX IF NOT EXISTS idx_aliases_language ON public.ingredient_aliases(language_code);
CREATE INDEX IF NOT EXISTS idx_aliases_name_search ON public.ingredient_aliases USING gin(to_tsvector('english', alias_name));

COMMENT ON TABLE public.ingredient_aliases IS 'Multi-language names and regional variations for ingredients';
COMMENT ON COLUMN public.ingredient_aliases.is_primary IS 'Primary display name for this language (one per language per ingredient)';
COMMENT ON COLUMN public.ingredient_aliases.usage_frequency IS 'Incremented each time this alias is searched';

-- Enable RLS
ALTER TABLE public.ingredient_aliases ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS ingredient_aliases_read_policy ON public.ingredient_aliases;
CREATE POLICY ingredient_aliases_read_policy ON public.ingredient_aliases
    FOR SELECT USING (true);

DROP POLICY IF EXISTS ingredient_aliases_write_policy ON public.ingredient_aliases;
CREATE POLICY ingredient_aliases_write_policy ON public.ingredient_aliases
    FOR ALL USING (auth.uid() IS NOT NULL);

-- ============================================================================
-- 3. Ingredient Images (Organized Image Repository)
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.ingredient_images (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ingredient_id UUID NOT NULL REFERENCES public.master_ingredients(id) ON DELETE CASCADE,
    
    -- Image identification
    image_id TEXT UNIQUE NOT NULL,
    
    -- Storage paths
    storage_uri TEXT NOT NULL, -- s3://bucket/path or supabase://bucket/path
    thumbnail_uri TEXT,
    
    -- Image context
    visual_state TEXT NOT NULL, -- raw_whole, raw_cut, chopped, powdered, cooked, packaged
    lighting_type TEXT, -- natural, indoor, studio, mixed
    background_type TEXT, -- market, kitchen, bowl, plate, white, wood
    angle TEXT, -- top, side, 45deg, closeup
    
    -- Image quality
    resolution_width INTEGER,
    resolution_height INTEGER,
    file_size_bytes BIGINT,
    
    -- Verification
    is_verified BOOLEAN DEFAULT false,
    verification_source TEXT, -- human, ai_confident, ai_uncertain, user_upload
    verified_at TIMESTAMPTZ,
    verified_by UUID REFERENCES auth.users(id),
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_images_ingredient ON public.ingredient_images(ingredient_id);
CREATE INDEX IF NOT EXISTS idx_images_state ON public.ingredient_images(visual_state);
CREATE INDEX IF NOT EXISTS idx_images_verified ON public.ingredient_images(is_verified) WHERE is_verified = true;

COMMENT ON TABLE public.ingredient_images IS 'Curated image repository for visual ingredient identification';
COMMENT ON COLUMN public.ingredient_images.visual_state IS 'Form of ingredient in image for training CV models';
COMMENT ON COLUMN public.ingredient_images.verification_source IS 'Source of verification for quality control';

-- Enable RLS
ALTER TABLE public.ingredient_images ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS ingredient_images_read_policy ON public.ingredient_images;
CREATE POLICY ingredient_images_read_policy ON public.ingredient_images
    FOR SELECT USING (true);

DROP POLICY IF EXISTS ingredient_images_write_policy ON public.ingredient_images;
CREATE POLICY ingredient_images_write_policy ON public.ingredient_images
    FOR ALL USING (auth.uid() IS NOT NULL);

-- ============================================================================
-- 4. Ingredient Substitutions (Directed Graph)
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.ingredient_substitutions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_ingredient_id UUID NOT NULL REFERENCES public.master_ingredients(id) ON DELETE CASCADE,
    target_ingredient_id UUID NOT NULL REFERENCES public.master_ingredients(id) ON DELETE CASCADE,
    
    -- Substitution relationship
    substitution_type TEXT NOT NULL, -- primary, emergency, regional, dietary, seasonal
    similarity_score NUMERIC(3,2) NOT NULL CHECK (similarity_score >= 0 AND similarity_score <= 1),
    
    -- Context filters
    applicable_forms TEXT[], -- fresh, dried, powdered (when substitution works)
    applicable_dishes TEXT[], -- curries, stews, marinades (where substitution works)
    applicable_cuisines TEXT[], -- indian, thai, mexican
    
    -- Conversion ratio
    conversion_ratio NUMERIC(4,2) DEFAULT 1.0, -- How much target to use (e.g., 0.75 means use 75% of source amount)
    conversion_notes TEXT,
    
    -- Usage tracking (learning system)
    times_suggested INTEGER DEFAULT 0,
    times_accepted INTEGER DEFAULT 0,
    times_rejected INTEGER DEFAULT 0,
    user_acceptance_rate NUMERIC(3,2) GENERATED ALWAYS AS (
        CASE 
            WHEN times_suggested > 0 
            THEN ROUND(times_accepted::numeric / times_suggested::numeric, 2)
            ELSE NULL
        END
    ) STORED,
    
    -- Notes
    notes TEXT,
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT unique_substitution UNIQUE(source_ingredient_id, target_ingredient_id, substitution_type),
    CONSTRAINT different_ingredients CHECK (source_ingredient_id != target_ingredient_id)
);

CREATE INDEX IF NOT EXISTS idx_substitutions_source ON public.ingredient_substitutions(source_ingredient_id);
CREATE INDEX IF NOT EXISTS idx_substitutions_target ON public.ingredient_substitutions(target_ingredient_id);
CREATE INDEX IF NOT EXISTS idx_substitutions_type ON public.ingredient_substitutions(substitution_type);
CREATE INDEX IF NOT EXISTS idx_substitutions_score ON public.ingredient_substitutions(similarity_score DESC);
CREATE INDEX IF NOT EXISTS idx_substitutions_acceptance ON public.ingredient_substitutions(user_acceptance_rate DESC NULLS LAST);

COMMENT ON TABLE public.ingredient_substitutions IS 'Directed graph of ingredient substitution relationships with learning';
COMMENT ON COLUMN public.ingredient_substitutions.substitution_type IS 'primary: best match, emergency: fallback, regional: local variant, dietary: allergen alternative';
COMMENT ON COLUMN public.ingredient_substitutions.similarity_score IS 'Flavor/texture similarity (0.0-1.0), higher is better';
COMMENT ON COLUMN public.ingredient_substitutions.user_acceptance_rate IS 'Auto-calculated from user feedback for continuous learning';

-- Enable RLS
ALTER TABLE public.ingredient_substitutions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS ingredient_substitutions_read_policy ON public.ingredient_substitutions;
CREATE POLICY ingredient_substitutions_read_policy ON public.ingredient_substitutions
    FOR SELECT USING (true);

DROP POLICY IF EXISTS ingredient_substitutions_write_policy ON public.ingredient_substitutions;
CREATE POLICY ingredient_substitutions_write_policy ON public.ingredient_substitutions
    FOR ALL USING (auth.uid() IS NOT NULL);

-- ============================================================================
-- 5. Ingredient Confusion (Disambiguation Graph)
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.ingredient_confusion (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ingredient_a_id UUID NOT NULL REFERENCES public.master_ingredients(id) ON DELETE CASCADE,
    ingredient_b_id UUID NOT NULL REFERENCES public.master_ingredients(id) ON DELETE CASCADE,
    
    -- Confusion details
    confusion_reason TEXT NOT NULL, -- similar_appearance, similar_name, same_category, packaging
    confusion_frequency INTEGER DEFAULT 0, -- Incremented when users confuse these
    
    -- Disambiguation
    disambiguation_rules TEXT[], -- ["A is more orange", "B has smoother skin"]
    key_visual_differences TEXT[], -- ["color_intensity", "surface_texture", "shape"]
    key_taste_differences TEXT[], -- ["A is bitter", "B is sweet"]
    
    -- Usage contexts
    commonly_confused_in TEXT[], -- raw_form, powdered_form, cooked_form
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT unique_confusion_pair UNIQUE(ingredient_a_id, ingredient_b_id),
    CONSTRAINT different_ingredients_confusion CHECK (ingredient_a_id < ingredient_b_id)
);

CREATE INDEX IF NOT EXISTS idx_confusion_a ON public.ingredient_confusion(ingredient_a_id);
CREATE INDEX IF NOT EXISTS idx_confusion_b ON public.ingredient_confusion(ingredient_b_id);
CREATE INDEX IF NOT EXISTS idx_confusion_frequency ON public.ingredient_confusion(confusion_frequency DESC);

COMMENT ON TABLE public.ingredient_confusion IS 'Commonly confused ingredient pairs with disambiguation rules';
COMMENT ON COLUMN public.ingredient_confusion.confusion_frequency IS 'How often users confuse these (incremented from user corrections)';
COMMENT ON COLUMN public.ingredient_confusion.disambiguation_rules IS 'Human-readable rules to distinguish ingredients';

-- Enable RLS
ALTER TABLE public.ingredient_confusion ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS ingredient_confusion_read_policy ON public.ingredient_confusion;
CREATE POLICY ingredient_confusion_read_policy ON public.ingredient_confusion
    FOR SELECT USING (true);

DROP POLICY IF EXISTS ingredient_confusion_write_policy ON public.ingredient_confusion;
CREATE POLICY ingredient_confusion_write_policy ON public.ingredient_confusion
    FOR ALL USING (auth.uid() IS NOT NULL);

-- ============================================================================
-- 6. Ingredient Pairings (Culinary Intelligence)
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.ingredient_pairings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ingredient_a_id UUID NOT NULL REFERENCES public.master_ingredients(id) ON DELETE CASCADE,
    ingredient_b_id UUID NOT NULL REFERENCES public.master_ingredients(id) ON DELETE CASCADE,
    
    -- Pairing strength
    pairing_score NUMERIC(3,2) NOT NULL CHECK (pairing_score >= 0 AND pairing_score <= 1),
    pairing_type TEXT NOT NULL, -- classic, modern, regional, experimental, traditional
    
    -- Context
    cuisine_types TEXT[], -- indian, italian, chinese, thai, mexican
    dish_types TEXT[], -- curry, pasta, stir_fry, soup, salad
    cooking_methods TEXT[], -- saute, roast, boil, grill, raw
    
    -- Evidence and source
    source TEXT NOT NULL, -- recipe_analysis, expert_knowledge, user_behavior, scientific
    times_used_together INTEGER DEFAULT 0,
    
    -- Synergy notes
    flavor_synergy TEXT, -- What makes this pairing work
    preparation_notes TEXT, -- How to use together
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT unique_pairing UNIQUE(ingredient_a_id, ingredient_b_id, pairing_type),
    CONSTRAINT different_ingredients_pairing CHECK (ingredient_a_id < ingredient_b_id)
);

CREATE INDEX IF NOT EXISTS idx_pairings_a ON public.ingredient_pairings(ingredient_a_id);
CREATE INDEX IF NOT EXISTS idx_pairings_b ON public.ingredient_pairings(ingredient_b_id);
CREATE INDEX IF NOT EXISTS idx_pairings_score ON public.ingredient_pairings(pairing_score DESC);
CREATE INDEX IF NOT EXISTS idx_pairings_type ON public.ingredient_pairings(pairing_type);

COMMENT ON TABLE public.ingredient_pairings IS 'Ingredient pairing recommendations for recipe suggestions';
COMMENT ON COLUMN public.ingredient_pairings.pairing_score IS 'Strength of pairing (0.0-1.0), based on culinary science and usage';
COMMENT ON COLUMN public.ingredient_pairings.source IS 'Evidence source for pairing recommendation';

-- Enable RLS
ALTER TABLE public.ingredient_pairings ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS ingredient_pairings_read_policy ON public.ingredient_pairings;
CREATE POLICY ingredient_pairings_read_policy ON public.ingredient_pairings
    FOR SELECT USING (true);

DROP POLICY IF EXISTS ingredient_pairings_write_policy ON public.ingredient_pairings;
CREATE POLICY ingredient_pairings_write_policy ON public.ingredient_pairings
    FOR ALL USING (auth.uid() IS NOT NULL);

-- ============================================================================
-- 7. Regional Variants (Geographic Intelligence)
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.ingredient_regional_variants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ingredient_id UUID NOT NULL REFERENCES public.master_ingredients(id) ON DELETE CASCADE,
    
    -- Location
    region TEXT NOT NULL, -- India, Thailand, Mexico, Mediterranean
    country_code TEXT, -- IN, TH, MX, IT
    sub_region TEXT, -- South India, Northern Mexico
    
    -- Variant details
    variant_notes TEXT,
    flavor_differences TEXT[], -- stronger, milder, sweeter, more_aromatic
    appearance_differences TEXT[], -- darker_color, larger_size, different_shape
    typical_uses TEXT[], -- everyday_cooking, festivals, medicinal
    
    -- Sourcing
    is_native BOOLEAN DEFAULT false,
    availability_level TEXT, -- abundant, common, rare, imported, seasonal
    harvest_season TEXT, -- monsoon, winter, spring, year_round
    
    -- Local names (reference to aliases table)
    primary_local_name TEXT,
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT unique_regional_variant UNIQUE(ingredient_id, region, country_code)
);

CREATE INDEX IF NOT EXISTS idx_variants_ingredient ON public.ingredient_regional_variants(ingredient_id);
CREATE INDEX IF NOT EXISTS idx_variants_region ON public.ingredient_regional_variants(region);
CREATE INDEX IF NOT EXISTS idx_variants_country ON public.ingredient_regional_variants(country_code);
CREATE INDEX IF NOT EXISTS idx_variants_availability ON public.ingredient_regional_variants(availability_level);

COMMENT ON TABLE public.ingredient_regional_variants IS 'Geographic variations of ingredients with local characteristics';
COMMENT ON COLUMN public.ingredient_regional_variants.is_native IS 'Whether ingredient is native to this region';
COMMENT ON COLUMN public.ingredient_regional_variants.availability_level IS 'How easy to find in this region';

-- Enable RLS
ALTER TABLE public.ingredient_regional_variants ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS ingredient_regional_variants_read_policy ON public.ingredient_regional_variants;
CREATE POLICY ingredient_regional_variants_read_policy ON public.ingredient_regional_variants
    FOR SELECT USING (true);

DROP POLICY IF EXISTS ingredient_regional_variants_write_policy ON public.ingredient_regional_variants;
CREATE POLICY ingredient_regional_variants_write_policy ON public.ingredient_regional_variants
    FOR ALL USING (auth.uid() IS NOT NULL);

-- ============================================================================
-- 8. Ingredient Embeddings (Vector Search) - Requires pgvector extension
-- ============================================================================

-- Note: Requires pgvector extension
-- Run manually: CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS public.ingredient_embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ingredient_id UUID NOT NULL REFERENCES public.master_ingredients(id) ON DELETE CASCADE,
    
    -- Vector data (uncomment after enabling pgvector)
    -- text_embedding VECTOR(1536), -- OpenAI ada-002 or similar
    -- image_embedding VECTOR(512), -- CLIP or similar
    
    -- For now, store as JSONB (can migrate to VECTOR later)
    text_embedding JSONB,
    image_embedding JSONB,
    
    -- Metadata
    embedding_model TEXT NOT NULL, -- openai/text-embedding-ada-002, clip-vit-base-patch32
    embedding_version TEXT,
    embedding_source TEXT, -- canonical_name, description, aliases, visual_features
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT unique_ingredient_embedding UNIQUE(ingredient_id, embedding_model)
);

CREATE INDEX IF NOT EXISTS idx_embeddings_ingredient ON public.ingredient_embeddings(ingredient_id);
CREATE INDEX IF NOT EXISTS idx_embeddings_model ON public.ingredient_embeddings(embedding_model);

-- Vector similarity indexes (uncomment after enabling pgvector)
-- CREATE INDEX IF NOT EXISTS idx_embeddings_text_vector ON public.ingredient_embeddings USING ivfflat (text_embedding vector_cosine_ops) WITH (lists = 100);
-- CREATE INDEX IF NOT EXISTS idx_embeddings_image_vector ON public.ingredient_embeddings USING ivfflat (image_embedding vector_cosine_ops) WITH (lists = 100);

COMMENT ON TABLE public.ingredient_embeddings IS 'Vector embeddings for semantic search and similarity matching';
COMMENT ON COLUMN public.ingredient_embeddings.text_embedding IS 'Text embedding from canonical name, aliases, and description';
COMMENT ON COLUMN public.ingredient_embeddings.image_embedding IS 'Image embedding from visual features';

-- Enable RLS
ALTER TABLE public.ingredient_embeddings ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS ingredient_embeddings_read_policy ON public.ingredient_embeddings;
CREATE POLICY ingredient_embeddings_read_policy ON public.ingredient_embeddings
    FOR SELECT USING (true);

DROP POLICY IF EXISTS ingredient_embeddings_write_policy ON public.ingredient_embeddings;
CREATE POLICY ingredient_embeddings_write_policy ON public.ingredient_embeddings
    FOR ALL USING (auth.uid() IS NOT NULL);

-- ============================================================================
-- 9. Visual Scan Results (CV Processing Logs & Learning)
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.visual_scan_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    
    -- Input data
    scan_image_url TEXT NOT NULL,
    scan_type TEXT NOT NULL, -- ingredient_identification, quality_check, quantity_estimate, freshness
    
    -- Detection results (top N candidates)
    detected_ingredients JSONB NOT NULL, -- [{"ingredient_id": "uuid", "confidence": 0.85, "canonical_name": "turmeric"}]
    visual_features JSONB, -- {"dominant_colors": ["yellow", "orange"], "texture": "grainy", "shape": "elongated"}
    
    -- User feedback (learning system)
    user_confirmed_ingredient_id UUID REFERENCES public.master_ingredients(id),
    user_confirmed_at TIMESTAMPTZ,
    was_correct BOOLEAN, -- Was top detection correct?
    correction_reason TEXT, -- confusion_with_X, poor_lighting, wrong_visual_state
    
    -- Performance metrics
    processing_time_ms INTEGER,
    model_version TEXT,
    confidence_top1 NUMERIC(3,2), -- Confidence of top detection
    confidence_top3_avg NUMERIC(3,2), -- Average confidence of top 3
    
    -- Context
    lighting_condition TEXT, -- natural, indoor, poor, mixed
    background_complexity TEXT, -- simple, medium, complex
    image_quality TEXT, -- high, medium, low
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_visual_scans_user ON public.visual_scan_results(user_id);
CREATE INDEX IF NOT EXISTS idx_visual_scans_type ON public.visual_scan_results(scan_type);
CREATE INDEX IF NOT EXISTS idx_visual_scans_confirmed ON public.visual_scan_results(user_confirmed_ingredient_id);
CREATE INDEX IF NOT EXISTS idx_visual_scans_correct ON public.visual_scan_results(was_correct) WHERE was_correct IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_visual_scans_created ON public.visual_scan_results(created_at DESC);

COMMENT ON TABLE public.visual_scan_results IS 'Visual ingredient identification results with user feedback for ML training';
COMMENT ON COLUMN public.visual_scan_results.detected_ingredients IS 'Top N candidate ingredients with confidence scores';
COMMENT ON COLUMN public.visual_scan_results.was_correct IS 'Whether top detection matched user confirmation (for accuracy tracking)';

-- Enable RLS
ALTER TABLE public.visual_scan_results ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS visual_scan_results_user_policy ON public.visual_scan_results;
CREATE POLICY visual_scan_results_user_policy ON public.visual_scan_results
    FOR ALL USING (auth.uid() = user_id);

-- ============================================================================
-- 10. Helper Functions for Intelligence Features
-- ============================================================================

-- Function: Get substitutions for an ingredient with context
DROP FUNCTION IF EXISTS get_ingredient_substitutions(UUID, TEXT, TEXT, TEXT);

CREATE OR REPLACE FUNCTION get_ingredient_substitutions(
    p_ingredient_id UUID,
    p_dish_type TEXT DEFAULT NULL,
    p_cuisine TEXT DEFAULT NULL,
    p_form TEXT DEFAULT NULL
)
RETURNS TABLE (
    substitution_id UUID,
    target_ingredient_id UUID,
    target_canonical_name TEXT,
    substitution_type TEXT,
    similarity_score NUMERIC,
    conversion_ratio NUMERIC,
    user_acceptance_rate NUMERIC,
    notes TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        s.id as substitution_id,
        s.target_ingredient_id,
        mi.canonical_name as target_canonical_name,
        s.substitution_type,
        s.similarity_score,
        s.conversion_ratio,
        s.user_acceptance_rate,
        s.notes
    FROM public.ingredient_substitutions s
    JOIN public.master_ingredients mi ON s.target_ingredient_id = mi.id
    WHERE s.source_ingredient_id = p_ingredient_id
        AND (p_form IS NULL OR p_form = ANY(s.applicable_forms))
        AND (p_dish_type IS NULL OR p_dish_type = ANY(s.applicable_dishes))
        AND (p_cuisine IS NULL OR p_cuisine = ANY(s.applicable_cuisines))
    ORDER BY 
        CASE s.substitution_type
            WHEN 'primary' THEN 1
            WHEN 'regional' THEN 2
            WHEN 'dietary' THEN 3
            WHEN 'emergency' THEN 4
            ELSE 5
        END,
        s.similarity_score DESC,
        s.user_acceptance_rate DESC NULLS LAST
    LIMIT 10;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION get_ingredient_substitutions IS 'Get ranked substitutions with optional context filtering';

-- Function: Get ingredient pairings
DROP FUNCTION IF EXISTS get_ingredient_pairings(UUID, TEXT, INTEGER);

CREATE OR REPLACE FUNCTION get_ingredient_pairings(
    p_ingredient_id UUID,
    p_cuisine_type TEXT DEFAULT NULL,
    p_limit INTEGER DEFAULT 10
)
RETURNS TABLE (
    pairing_id UUID,
    paired_ingredient_id UUID,
    paired_canonical_name TEXT,
    pairing_score NUMERIC,
    pairing_type TEXT,
    flavor_synergy TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        p.id as pairing_id,
        CASE 
            WHEN p.ingredient_a_id = p_ingredient_id THEN p.ingredient_b_id
            ELSE p.ingredient_a_id
        END as paired_ingredient_id,
        mi.canonical_name as paired_canonical_name,
        p.pairing_score,
        p.pairing_type,
        p.flavor_synergy
    FROM public.ingredient_pairings p
    JOIN public.master_ingredients mi ON (
        CASE 
            WHEN p.ingredient_a_id = p_ingredient_id THEN p.ingredient_b_id
            ELSE p.ingredient_a_id
        END = mi.id
    )
    WHERE (p.ingredient_a_id = p_ingredient_id OR p.ingredient_b_id = p_ingredient_id)
        AND (p_cuisine_type IS NULL OR p_cuisine_type = ANY(p.cuisine_types))
    ORDER BY p.pairing_score DESC, p.times_used_together DESC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION get_ingredient_pairings IS 'Get ingredient pairings ranked by score and usage';

-- Function: Search ingredients with multi-language alias support
DROP FUNCTION IF EXISTS search_ingredients_with_aliases(TEXT, TEXT, INTEGER);

CREATE OR REPLACE FUNCTION search_ingredients_with_aliases(
    search_query TEXT,
    search_lang TEXT DEFAULT 'en',
    limit_count INTEGER DEFAULT 20
)
RETURNS TABLE (
    id UUID,
    canonical_name TEXT,
    matched_name TEXT,
    match_source TEXT,
    match_language TEXT,
    category TEXT,
    default_image_url TEXT,
    relevance NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    WITH alias_matches AS (
        SELECT 
            a.ingredient_id,
            a.alias_name as matched_name,
            'alias' as match_source,
            a.language_code as match_language,
            CASE 
                WHEN a.is_primary THEN 1.0
                WHEN a.language_code = search_lang THEN 0.9
                ELSE 0.7
            END as relevance
        FROM public.ingredient_aliases a
        WHERE a.alias_name ILIKE '%' || search_query || '%'
            AND (search_lang IS NULL OR a.language_code = search_lang)
    ),
    master_matches AS (
        SELECT 
            mi.id as ingredient_id,
            mi.canonical_name as matched_name,
            'canonical' as match_source,
            'en' as match_language,
            CASE 
                WHEN mi.canonical_name ILIKE search_query || '%' THEN 1.0
                WHEN mi.canonical_name ILIKE '%' || search_query || '%' THEN 0.8
                ELSE 0.5
            END as relevance
        FROM public.master_ingredients mi
        WHERE mi.canonical_name ILIKE '%' || search_query || '%'
    )
    SELECT DISTINCT ON (mi.id)
        mi.id,
        mi.canonical_name,
        COALESCE(am.matched_name, mm.matched_name, mi.canonical_name) as matched_name,
        COALESCE(am.match_source, mm.match_source, 'canonical') as match_source,
        COALESCE(am.match_language, mm.match_language, 'en') as match_language,
        mi.category,
        mi.default_image_url,
        COALESCE(GREATEST(am.relevance, mm.relevance), 0.5) as relevance
    FROM public.master_ingredients mi
    LEFT JOIN alias_matches am ON am.ingredient_id = mi.id
    LEFT JOIN master_matches mm ON mm.ingredient_id = mi.id
    WHERE am.ingredient_id IS NOT NULL OR mm.ingredient_id IS NOT NULL
    ORDER BY mi.id, relevance DESC
    LIMIT limit_count;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION search_ingredients_with_aliases IS 'Enhanced multi-language search including aliases table';

-- ============================================================================
-- MIGRATION COMPLETE
-- ============================================================================

-- Summary
COMMENT ON SCHEMA public IS 'SAVO Ingredient Intelligence System - Phase 1 Complete';
