-- Global Ingredients Database and Barcode Scanning
-- Date: 2026-01-06
-- Purpose: Master ingredient reference, barcode database, and quantity estimation

-- ============================================================================
-- 1. Master Ingredients Table with Multi-Language Support
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.master_ingredients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_name TEXT UNIQUE NOT NULL,
    
    -- Multi-language names: {"en": "Rice", "hi": "चावल", "ta": "அரிசி", "es": "Arroz", "zh": "米饭", "ar": "أرز"}
    names JSONB NOT NULL DEFAULT '{}'::jsonb,
    
    -- Category and classification
    category TEXT NOT NULL, -- vegetables, grains, spices, dairy, meat, etc.
    subcategory TEXT,
    
    -- Visual and storage information
    typical_containers TEXT[] DEFAULT ARRAY['package'], -- package, jar, bottle, loose, bag, box
    default_image_url TEXT,
    color_hints TEXT[], -- ["white", "brown"] for rice varieties
    texture_hints TEXT[], -- ["grainy", "powdery", "solid"]
    
    -- Physical properties for quantity estimation
    density_g_per_ml NUMERIC(6,3), -- 0.75 for rice, 0.6 for flour
    typical_package_sizes NUMERIC[] DEFAULT ARRAY[500, 1000, 2000], -- grams
    
    -- Barcode patterns by country
    barcode_prefixes TEXT[], -- ["89" for India, "05" for USA]
    common_brands JSONB DEFAULT '{}'::jsonb, -- {"India": ["Amul", "Nestle"], "USA": ["Kraft"]}
    
    -- Nutritional reference (per 100g)
    nutrition_per_100g JSONB,
    
    -- Metadata
    is_verified BOOLEAN DEFAULT false,
    created_by UUID REFERENCES auth.users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_master_ingredients_canonical ON public.master_ingredients(canonical_name);
CREATE INDEX IF NOT EXISTS idx_master_ingredients_category ON public.master_ingredients(category);
CREATE INDEX IF NOT EXISTS idx_master_ingredients_names ON public.master_ingredients USING gin(names);

COMMENT ON TABLE public.master_ingredients IS 'Global ingredient database with multi-language support';
COMMENT ON COLUMN public.master_ingredients.names IS 'Multi-language names in JSONB: {en, hi, ta, es, zh, ar}';
COMMENT ON COLUMN public.master_ingredients.density_g_per_ml IS 'Density for volume-to-weight conversion';

-- Enable RLS
ALTER TABLE public.master_ingredients ENABLE ROW LEVEL SECURITY;

-- Anyone can read master ingredients
DROP POLICY IF EXISTS master_ingredients_read_policy ON public.master_ingredients;
CREATE POLICY master_ingredients_read_policy ON public.master_ingredients
    FOR SELECT USING (true);

-- Only authenticated users can suggest new ingredients
DROP POLICY IF EXISTS master_ingredients_insert_policy ON public.master_ingredients;
CREATE POLICY master_ingredients_insert_policy ON public.master_ingredients
    FOR INSERT WITH CHECK (auth.uid() IS NOT NULL);

-- ============================================================================
-- 2. Product Barcodes Table (UPC/EAN Database)
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.product_barcodes (
    upc_ean TEXT PRIMARY KEY
);

-- Add columns WITHOUT foreign keys first
DO $$ 
BEGIN
    ALTER TABLE public.product_barcodes ADD COLUMN IF NOT EXISTS ingredient_id UUID;
    ALTER TABLE public.product_barcodes ADD COLUMN IF NOT EXISTS product_name TEXT;
    ALTER TABLE public.product_barcodes ADD COLUMN IF NOT EXISTS brand TEXT;
    ALTER TABLE public.product_barcodes ADD COLUMN IF NOT EXISTS manufacturer TEXT;
    ALTER TABLE public.product_barcodes ADD COLUMN IF NOT EXISTS country_code TEXT;
    ALTER TABLE public.product_barcodes ADD COLUMN IF NOT EXISTS quantity_value NUMERIC;
    ALTER TABLE public.product_barcodes ADD COLUMN IF NOT EXISTS quantity_unit TEXT;
    ALTER TABLE public.product_barcodes ADD COLUMN IF NOT EXISTS package_type TEXT;
    ALTER TABLE public.product_barcodes ADD COLUMN IF NOT EXISTS expiry_date_format TEXT;
    ALTER TABLE public.product_barcodes ADD COLUMN IF NOT EXISTS nutrition_facts JSONB;
    ALTER TABLE public.product_barcodes ADD COLUMN IF NOT EXISTS data_source TEXT;
    ALTER TABLE public.product_barcodes ADD COLUMN IF NOT EXISTS external_id TEXT;
    ALTER TABLE public.product_barcodes ADD COLUMN IF NOT EXISTS confidence NUMERIC(3,2);
    ALTER TABLE public.product_barcodes ADD COLUMN IF NOT EXISTS image_url TEXT;
    ALTER TABLE public.product_barcodes ADD COLUMN IF NOT EXISTS last_scanned_at TIMESTAMPTZ;
    ALTER TABLE public.product_barcodes ADD COLUMN IF NOT EXISTS scan_count INTEGER;
    ALTER TABLE public.product_barcodes ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ;
    ALTER TABLE public.product_barcodes ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ;
END $$;

-- Set defaults
ALTER TABLE public.product_barcodes ALTER COLUMN data_source SET DEFAULT 'openfoodfacts';
ALTER TABLE public.product_barcodes ALTER COLUMN confidence SET DEFAULT 0.95;
ALTER TABLE public.product_barcodes ALTER COLUMN scan_count SET DEFAULT 0;
ALTER TABLE public.product_barcodes ALTER COLUMN created_at SET DEFAULT NOW();
ALTER TABLE public.product_barcodes ALTER COLUMN updated_at SET DEFAULT NOW();

-- Add foreign key constraint if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname = 'product_barcodes_ingredient_id_fkey'
    ) THEN
        ALTER TABLE public.product_barcodes 
        ADD CONSTRAINT product_barcodes_ingredient_id_fkey 
        FOREIGN KEY (ingredient_id) REFERENCES public.master_ingredients(id) ON DELETE SET NULL;
    END IF;
END $$;

-- Update product_name to NOT NULL only if it's NULL
UPDATE public.product_barcodes SET product_name = 'Unknown' WHERE product_name IS NULL;
DO $$
BEGIN
    ALTER TABLE public.product_barcodes ALTER COLUMN product_name SET NOT NULL;
EXCEPTION
    WHEN others THEN NULL; -- Ignore if already NOT NULL
END $$;

CREATE INDEX IF NOT EXISTS idx_product_barcodes_ingredient ON public.product_barcodes(ingredient_id);
CREATE INDEX IF NOT EXISTS idx_product_barcodes_country ON public.product_barcodes(country_code);
CREATE INDEX IF NOT EXISTS idx_product_barcodes_brand ON public.product_barcodes(brand);

COMMENT ON TABLE public.product_barcodes IS 'UPC/EAN barcode database linked to master ingredients';
COMMENT ON COLUMN public.product_barcodes.expiry_date_format IS 'Pattern to parse expiry date from package';

-- Enable RLS
ALTER TABLE public.product_barcodes ENABLE ROW LEVEL SECURITY;

-- Anyone can read barcodes
DROP POLICY IF EXISTS product_barcodes_read_policy ON public.product_barcodes;
CREATE POLICY product_barcodes_read_policy ON public.product_barcodes
    FOR SELECT USING (true);

-- Authenticated users can add barcodes
DROP POLICY IF EXISTS product_barcodes_insert_policy ON public.product_barcodes;
CREATE POLICY product_barcodes_insert_policy ON public.product_barcodes
    FOR INSERT WITH CHECK (auth.uid() IS NOT NULL);

-- ============================================================================
-- 3. Ingredient Densities Lookup Table
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.ingredient_densities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ingredient_id UUID REFERENCES public.master_ingredients(id) ON DELETE CASCADE,
    
    -- Density variations by form
    form TEXT NOT NULL, -- cooked, raw, packed, loose, powdered
    density_g_per_ml NUMERIC(6,3) NOT NULL,
    
    -- Examples for calibration
    example_volume_ml NUMERIC,
    example_weight_g NUMERIC,
    
    -- Metadata
    source TEXT, -- USDA, manual_measurement, user_calibration
    confidence NUMERIC(3,2) DEFAULT 0.80,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ingredient_densities_ingredient ON public.ingredient_densities(ingredient_id);
CREATE INDEX IF NOT EXISTS idx_ingredient_densities_form ON public.ingredient_densities(form);

COMMENT ON TABLE public.ingredient_densities IS 'Density lookup for different ingredient forms';

-- Enable RLS
ALTER TABLE public.ingredient_densities ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS ingredient_densities_read_policy ON public.ingredient_densities;
CREATE POLICY ingredient_densities_read_policy ON public.ingredient_densities
    FOR SELECT USING (true);

-- ============================================================================
-- 4. Quantity Calibration Data (ML Training Data)
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.quantity_calibrations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    ingredient_id UUID REFERENCES public.master_ingredients(id) ON DELETE SET NULL,
    
    -- Image and detection data
    image_url TEXT NOT NULL,
    bbox JSONB, -- Bounding box of ingredient
    container_type TEXT, -- jar, bottle, bowl, plate, bag, loose
    
    -- Reference objects detected
    reference_objects JSONB, -- [{"type": "hand", "size_cm": 18}, {"type": "coin", "size_cm": 2.5}]
    
    -- Quantity data
    estimated_quantity NUMERIC NOT NULL,
    estimated_unit TEXT NOT NULL,
    actual_quantity NUMERIC, -- User-confirmed actual weight
    actual_unit TEXT,
    
    -- Confidence and accuracy
    confidence NUMERIC(3,2),
    estimation_method TEXT, -- bbox_volume, reference_object, ml_model, user_input
    error_percentage NUMERIC(5,2), -- ABS((estimated - actual) / actual * 100)
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_quantity_calibrations_user ON public.quantity_calibrations(user_id);
CREATE INDEX IF NOT EXISTS idx_quantity_calibrations_ingredient ON public.quantity_calibrations(ingredient_id);
CREATE INDEX IF NOT EXISTS idx_quantity_calibrations_container ON public.quantity_calibrations(container_type);

COMMENT ON TABLE public.quantity_calibrations IS 'Training data for quantity estimation ML model';
COMMENT ON COLUMN public.quantity_calibrations.error_percentage IS 'Accuracy metric for model improvement';

-- Enable RLS
ALTER TABLE public.quantity_calibrations ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS quantity_calibrations_user_policy ON public.quantity_calibrations;
CREATE POLICY quantity_calibrations_user_policy ON public.quantity_calibrations
    FOR ALL USING (auth.uid() = user_id);

-- ============================================================================
-- 5. Container Recognition Results
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.container_scans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    
    -- Image data
    image_url TEXT NOT NULL,
    scan_type TEXT DEFAULT 'container', -- container, transparent_jar, glass_bottle
    
    -- Detection results
    container_type TEXT, -- mason_jar, plastic_container, glass_jar, ziplock_bag
    container_material TEXT, -- glass, plastic, metal
    transparency_level TEXT, -- transparent, translucent, opaque
    
    -- Ingredient identification
    detected_ingredient_id UUID REFERENCES public.master_ingredients(id),
    detected_ingredient_name TEXT,
    visual_cues JSONB, -- {"color": "white", "texture": "grainy", "size": "small_grains"}
    
    -- Quantity estimation
    estimated_fill_percentage NUMERIC(5,2), -- 75.5% full
    estimated_container_volume_ml NUMERIC,
    estimated_quantity NUMERIC,
    estimated_unit TEXT,
    
    -- Confidence scores
    confidence_ingredient NUMERIC(3,2),
    confidence_container NUMERIC(3,2),
    confidence_quantity NUMERIC(3,2),
    
    -- User confirmation
    confirmation_status TEXT DEFAULT 'pending', -- pending, confirmed, corrected, rejected
    actual_ingredient TEXT,
    actual_quantity NUMERIC,
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_container_scans_user ON public.container_scans(user_id);
CREATE INDEX IF NOT EXISTS idx_container_scans_ingredient ON public.container_scans(detected_ingredient_id);
CREATE INDEX IF NOT EXISTS idx_container_scans_type ON public.container_scans(container_type);

COMMENT ON TABLE public.container_scans IS 'Container-based ingredient recognition results';
COMMENT ON COLUMN public.container_scans.visual_cues IS 'Visual characteristics used for identification';

-- Enable RLS
ALTER TABLE public.container_scans ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS container_scans_user_policy ON public.container_scans;
CREATE POLICY container_scans_user_policy ON public.container_scans
    FOR ALL USING (auth.uid() = user_id);

-- ============================================================================
-- 6. Barcode Scan History
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.barcode_scans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE
);

-- Add columns without foreign keys
DO $$
BEGIN
    ALTER TABLE public.barcode_scans ADD COLUMN IF NOT EXISTS barcode TEXT;
    ALTER TABLE public.barcode_scans ADD COLUMN IF NOT EXISTS barcode_type TEXT;
    ALTER TABLE public.barcode_scans ADD COLUMN IF NOT EXISTS product_barcode TEXT;
    ALTER TABLE public.barcode_scans ADD COLUMN IF NOT EXISTS product_name TEXT;
    ALTER TABLE public.barcode_scans ADD COLUMN IF NOT EXISTS brand TEXT;
    ALTER TABLE public.barcode_scans ADD COLUMN IF NOT EXISTS quantity_value NUMERIC;
    ALTER TABLE public.barcode_scans ADD COLUMN IF NOT EXISTS quantity_unit TEXT;
    ALTER TABLE public.barcode_scans ADD COLUMN IF NOT EXISTS expiry_date DATE;
    ALTER TABLE public.barcode_scans ADD COLUMN IF NOT EXISTS expiry_date_raw TEXT;
    ALTER TABLE public.barcode_scans ADD COLUMN IF NOT EXISTS image_url TEXT;
    ALTER TABLE public.barcode_scans ADD COLUMN IF NOT EXISTS package_image_url TEXT;
    ALTER TABLE public.barcode_scans ADD COLUMN IF NOT EXISTS added_to_inventory BOOLEAN;
    ALTER TABLE public.barcode_scans ADD COLUMN IF NOT EXISTS inventory_item_id UUID;
    ALTER TABLE public.barcode_scans ADD COLUMN IF NOT EXISTS confidence NUMERIC(3,2);
    ALTER TABLE public.barcode_scans ADD COLUMN IF NOT EXISTS data_source TEXT;
    ALTER TABLE public.barcode_scans ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ;
END $$;

-- Set defaults
ALTER TABLE public.barcode_scans ALTER COLUMN added_to_inventory SET DEFAULT false;
ALTER TABLE public.barcode_scans ALTER COLUMN created_at SET DEFAULT NOW();

-- Add foreign key constraints
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'barcode_scans_product_barcode_fkey'
    ) THEN
        ALTER TABLE public.barcode_scans 
        ADD CONSTRAINT barcode_scans_product_barcode_fkey 
        FOREIGN KEY (product_barcode) REFERENCES public.product_barcodes(upc_ean) ON DELETE SET NULL;
    END IF;
    
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'barcode_scans_inventory_item_id_fkey'
    ) THEN
        ALTER TABLE public.barcode_scans 
        ADD CONSTRAINT barcode_scans_inventory_item_id_fkey 
        FOREIGN KEY (inventory_item_id) REFERENCES public.inventory_items(id) ON DELETE SET NULL;
    END IF;
END $$;

-- Set barcode NOT NULL if possible
UPDATE public.barcode_scans SET barcode = 'unknown' WHERE barcode IS NULL;
DO $$
BEGIN
    ALTER TABLE public.barcode_scans ALTER COLUMN barcode SET NOT NULL;
EXCEPTION
    WHEN others THEN NULL;
END $$;

CREATE INDEX IF NOT EXISTS idx_barcode_scans_user ON public.barcode_scans(user_id);
CREATE INDEX IF NOT EXISTS idx_barcode_scans_barcode ON public.barcode_scans(barcode);
CREATE INDEX IF NOT EXISTS idx_barcode_scans_product ON public.barcode_scans(product_barcode);

COMMENT ON TABLE public.barcode_scans IS 'History of barcode scans by users';

-- Enable RLS
ALTER TABLE public.barcode_scans ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS barcode_scans_user_policy ON public.barcode_scans;
CREATE POLICY barcode_scans_user_policy ON public.barcode_scans
    FOR ALL USING (auth.uid() = user_id);

-- ============================================================================
-- 7. Reference Objects Database (for size estimation)
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.reference_objects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    object_type TEXT UNIQUE NOT NULL, -- hand, coin, credit_card, phone, spoon, fork
    
    -- Average dimensions
    avg_length_cm NUMERIC(5,2),
    avg_width_cm NUMERIC(5,2),
    avg_height_cm NUMERIC(5,2),
    avg_volume_ml NUMERIC,
    
    -- Variations by region
    variations JSONB, -- {"adult_male": {"length_cm": 18.5}, "adult_female": {"length_cm": 16.8}}
    
    -- Visual characteristics for detection
    color_patterns TEXT[],
    shape_hints TEXT[],
    
    -- Metadata
    confidence_multiplier NUMERIC(3,2) DEFAULT 0.85, -- How reliable is this reference
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_reference_objects_type ON public.reference_objects(object_type);

COMMENT ON TABLE public.reference_objects IS 'Standard reference objects for size estimation';

-- Enable RLS
ALTER TABLE public.reference_objects ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS reference_objects_read_policy ON public.reference_objects;
CREATE POLICY reference_objects_read_policy ON public.reference_objects
    FOR SELECT USING (true);

-- ============================================================================
-- 8. Add expiry tracking to inventory_items
-- ============================================================================
ALTER TABLE public.inventory_items
ADD COLUMN IF NOT EXISTS expiry_date DATE,
ADD COLUMN IF NOT EXISTS purchase_date DATE,
ADD COLUMN IF NOT EXISTS barcode TEXT;

COMMENT ON COLUMN public.inventory_items.expiry_date IS 'Expiry date from package or barcode';

CREATE INDEX IF NOT EXISTS idx_inventory_items_expiry ON public.inventory_items(expiry_date) 
WHERE expiry_date IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_inventory_items_barcode ON public.inventory_items(barcode) 
WHERE barcode IS NOT NULL;

-- ============================================================================
-- 9. Functions for multi-language ingredient search
-- ============================================================================
DROP FUNCTION IF EXISTS search_ingredients_multilang(TEXT, TEXT, INTEGER);

CREATE OR REPLACE FUNCTION search_ingredients_multilang(
    search_query TEXT,
    search_lang TEXT DEFAULT 'en',
    limit_count INTEGER DEFAULT 20
)
RETURNS TABLE (
    id UUID,
    canonical_name TEXT,
    matched_name TEXT,
    match_language TEXT,
    category TEXT,
    default_image_url TEXT,
    relevance NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        mi.id,
        mi.canonical_name,
        COALESCE(mi.names->>search_lang, mi.names->>'en', mi.canonical_name) as matched_name,
        search_lang as match_language,
        mi.category,
        mi.default_image_url,
        CASE 
            WHEN mi.canonical_name ILIKE '%' || search_query || '%' THEN 1.0
            WHEN mi.names->>search_lang ILIKE '%' || search_query || '%' THEN 0.9
            WHEN mi.names->>'en' ILIKE '%' || search_query || '%' THEN 0.8
            ELSE 0.5
        END as relevance
    FROM public.master_ingredients mi
    WHERE 
        mi.canonical_name ILIKE '%' || search_query || '%'
        OR mi.names->>search_lang ILIKE '%' || search_query || '%'
        OR mi.names->>'en' ILIKE '%' || search_query || '%'
        OR EXISTS (
            SELECT 1 FROM jsonb_each_text(mi.names) AS n(k, v)
            WHERE v ILIKE '%' || search_query || '%'
        )
    ORDER BY relevance DESC, mi.canonical_name
    LIMIT limit_count;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION search_ingredients_multilang IS 'Search ingredients in any language';

-- ============================================================================
-- 10. Function to get ingredient by barcode
-- ============================================================================
DROP FUNCTION IF EXISTS get_ingredient_by_barcode(TEXT);

CREATE OR REPLACE FUNCTION get_ingredient_by_barcode(barcode_input TEXT)
RETURNS TABLE (
    ingredient_id UUID,
    canonical_name TEXT,
    product_name TEXT,
    brand TEXT,
    quantity_value NUMERIC,
    quantity_unit TEXT,
    default_image_url TEXT,
    package_image_url TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        mi.id as ingredient_id,
        mi.canonical_name,
        pb.product_name,
        pb.brand,
        pb.quantity_value,
        pb.quantity_unit,
        mi.default_image_url,
        pb.image_url as package_image_url
    FROM public.product_barcodes pb
    LEFT JOIN public.master_ingredients mi ON pb.ingredient_id = mi.id
    WHERE pb.upc_ean = barcode_input;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION get_ingredient_by_barcode IS 'Lookup product details by barcode';

-- ============================================================================
-- 11. Function to estimate quantity from volume
-- ============================================================================
DROP FUNCTION IF EXISTS estimate_quantity_from_volume(TEXT, NUMERIC, TEXT);

CREATE OR REPLACE FUNCTION estimate_quantity_from_volume(
    ingredient_canonical_name TEXT,
    volume_ml NUMERIC,
    ingredient_form TEXT DEFAULT 'raw'
)
RETURNS TABLE (
    estimated_weight_g NUMERIC,
    unit TEXT,
    confidence NUMERIC
) AS $$
DECLARE
    density NUMERIC;
    conf NUMERIC;
BEGIN
    -- Get density for the ingredient
    SELECT id.density_g_per_ml, id.confidence
    INTO density, conf
    FROM public.ingredient_densities id
    JOIN public.master_ingredients mi ON id.ingredient_id = mi.id
    WHERE mi.canonical_name = ingredient_canonical_name
        AND id.form = ingredient_form
    LIMIT 1;
    
    -- Fallback to master_ingredients density
    IF density IS NULL THEN
        SELECT mi.density_g_per_ml
        INTO density
        FROM public.master_ingredients mi
        WHERE mi.canonical_name = ingredient_canonical_name;
        
        conf := 0.70; -- Lower confidence for fallback
    END IF;
    
    IF density IS NOT NULL THEN
        RETURN QUERY
        SELECT 
            ROUND(volume_ml * density, 2) as estimated_weight_g,
            'g'::TEXT as unit,
            COALESCE(conf, 0.75) as confidence;
    ELSE
        RETURN QUERY
        SELECT 
            NULL::NUMERIC as estimated_weight_g,
            NULL::TEXT as unit,
            0.0::NUMERIC as confidence;
    END IF;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION estimate_quantity_from_volume IS 'Convert volume to weight using density lookup';
