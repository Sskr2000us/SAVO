-- Migration 003: Add Quantity Support to Vision Scanning System
-- Date: January 2, 2026
-- Purpose: Enable quantity tracking for ingredients to support serving size calculations

-- ============================================================================
-- SECTION 1: Add Quantity Columns to Existing Tables
-- ============================================================================

-- Add quantity tracking to user_pantry (idempotent - safe to re-run)
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='user_pantry' AND column_name='quantity') THEN
        ALTER TABLE user_pantry ADD COLUMN quantity DECIMAL(10,2);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='user_pantry' AND column_name='unit') THEN
        ALTER TABLE user_pantry ADD COLUMN unit VARCHAR(50);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='user_pantry' AND column_name='estimated') THEN
        ALTER TABLE user_pantry ADD COLUMN estimated BOOLEAN DEFAULT false;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='user_pantry' AND column_name='quantity_confidence') THEN
        ALTER TABLE user_pantry ADD COLUMN quantity_confidence DECIMAL(3,2);
    END IF;
END $$;

-- Add detected quantities to detected_ingredients (idempotent)
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='detected_ingredients' AND column_name='detected_quantity') THEN
        ALTER TABLE detected_ingredients ADD COLUMN detected_quantity DECIMAL(10,2);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='detected_ingredients' AND column_name='detected_unit') THEN
        ALTER TABLE detected_ingredients ADD COLUMN detected_unit VARCHAR(50);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='detected_ingredients' AND column_name='quantity_confidence') THEN
        ALTER TABLE detected_ingredients ADD COLUMN quantity_confidence DECIMAL(3,2);
    END IF;
END $$;

-- Add comments
COMMENT ON COLUMN user_pantry.quantity IS 'Amount of ingredient available';
COMMENT ON COLUMN user_pantry.unit IS 'Unit of measurement (grams, ml, pieces, cups, etc)';
COMMENT ON COLUMN user_pantry.estimated IS 'True if quantity was auto-estimated, false if user-entered';
COMMENT ON COLUMN user_pantry.quantity_confidence IS 'Confidence score 0-1 for estimated quantities';

COMMENT ON COLUMN detected_ingredients.detected_quantity IS 'Quantity detected from image (OCR or visual estimation)';
COMMENT ON COLUMN detected_ingredients.detected_unit IS 'Unit detected from image';
COMMENT ON COLUMN detected_ingredients.quantity_confidence IS 'Confidence score 0-1 for quantity detection';

-- ============================================================================
-- SECTION 2: Create Quantity Units Reference Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS quantity_units (
    id SERIAL PRIMARY KEY,
    unit_name VARCHAR(50) UNIQUE NOT NULL,
    category VARCHAR(20) NOT NULL,  -- 'weight', 'volume', 'count'
    base_unit VARCHAR(50) NOT NULL,  -- for conversion reference
    conversion_factor DECIMAL(10,6) NOT NULL,
    display_name VARCHAR(50),  -- user-friendly name
    display_order INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Add comment
COMMENT ON TABLE quantity_units IS 'Reference table for supported units and conversions';

-- Insert common units (idempotent - safe to re-run)
INSERT INTO quantity_units (unit_name, category, base_unit, conversion_factor, display_name, display_order) VALUES
-- Weight units (base: grams)
('grams', 'weight', 'grams', 1.0, 'g', 1),
('kg', 'weight', 'grams', 1000.0, 'kg', 2),
('oz', 'weight', 'grams', 28.3495, 'oz', 3),
('lb', 'weight', 'grams', 453.592, 'lb', 4),
('mg', 'weight', 'grams', 0.001, 'mg', 5),

-- Volume units (base: ml)
('ml', 'volume', 'ml', 1.0, 'ml', 6),
('liters', 'volume', 'ml', 1000.0, 'L', 7),
('cups', 'volume', 'ml', 236.588, 'cup', 8),
('tbsp', 'volume', 'ml', 14.7868, 'tbsp', 9),
('tsp', 'volume', 'ml', 4.92892, 'tsp', 10),
('fl oz', 'volume', 'ml', 29.5735, 'fl oz', 11),
('gallon', 'volume', 'ml', 3785.41, 'gal', 12),
('pint', 'volume', 'ml', 473.176, 'pt', 13),
('quart', 'volume', 'ml', 946.353, 'qt', 14),

-- Count units (base: pieces)
('pieces', 'count', 'pieces', 1.0, 'pcs', 15),
('items', 'count', 'pieces', 1.0, 'items', 16),
('cloves', 'count', 'pieces', 1.0, 'cloves', 17),
('slices', 'count', 'pieces', 1.0, 'slices', 18),
('leaves', 'count', 'pieces', 1.0, 'leaves', 19),
('cans', 'count', 'pieces', 1.0, 'cans', 20),
('packages', 'count', 'pieces', 1.0, 'pkgs', 21)
ON CONFLICT (unit_name) DO NOTHING;

-- Create index for fast lookups
CREATE INDEX IF NOT EXISTS idx_quantity_units_category ON quantity_units(category);
CREATE INDEX IF NOT EXISTS idx_quantity_units_display_order ON quantity_units(display_order);

-- ============================================================================
-- SECTION 3: Create Standard Serving Sizes Reference Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS standard_serving_sizes (
    id SERIAL PRIMARY KEY,
    ingredient_name VARCHAR(255) UNIQUE NOT NULL,
    category VARCHAR(100),  -- 'protein', 'vegetable', 'carb', 'dairy'
    serving_size DECIMAL(10,2) NOT NULL,  -- per person
    unit VARCHAR(50) NOT NULL,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Add comment
COMMENT ON TABLE standard_serving_sizes IS 'Standard serving sizes per person for common ingredients';

-- Insert standard serving sizes (per person) - idempotent
INSERT INTO standard_serving_sizes (ingredient_name, category, serving_size, unit, notes) VALUES
-- Proteins
('chicken', 'protein', 150, 'grams', 'Boneless chicken breast/thigh'),
('chicken_breast', 'protein', 150, 'grams', 'Boneless chicken breast'),
('beef', 'protein', 150, 'grams', 'Beef cuts'),
('ground_beef', 'protein', 120, 'grams', 'Ground/minced beef'),
('fish', 'protein', 120, 'grams', 'Fish fillet'),
('salmon', 'protein', 120, 'grams', 'Salmon fillet'),
('pork', 'protein', 150, 'grams', 'Pork cuts'),
('lamb', 'protein', 150, 'grams', 'Lamb cuts'),
('tofu', 'protein', 100, 'grams', 'Firm tofu'),
('shrimp', 'protein', 100, 'grams', 'Peeled shrimp'),
('eggs', 'protein', 2, 'pieces', 'Whole eggs'),

-- Vegetables
('tomato', 'vegetable', 80, 'grams', 'Fresh tomatoes'),
('onion', 'vegetable', 60, 'grams', 'One medium onion ~ 150g'),
('carrot', 'vegetable', 60, 'grams', 'Fresh carrots'),
('potato', 'vegetable', 150, 'grams', 'One medium potato ~ 150-200g'),
('bell_pepper', 'vegetable', 75, 'grams', 'One medium pepper ~ 150g'),
('spinach', 'vegetable', 60, 'grams', 'Fresh spinach'),
('broccoli', 'vegetable', 80, 'grams', 'Fresh broccoli'),
('cauliflower', 'vegetable', 80, 'grams', 'Fresh cauliflower'),
('zucchini', 'vegetable', 100, 'grams', 'One medium zucchini ~ 200g'),
('eggplant', 'vegetable', 100, 'grams', 'Eggplant/aubergine'),
('lettuce', 'vegetable', 50, 'grams', 'Lettuce leaves'),
('cucumber', 'vegetable', 60, 'grams', 'Fresh cucumber'),
('mushroom', 'vegetable', 50, 'grams', 'Button mushrooms'),

-- Carbs
('rice', 'carb', 60, 'grams', 'Dry weight rice'),
('basmati_rice', 'carb', 60, 'grams', 'Dry weight basmati'),
('pasta', 'carb', 80, 'grams', 'Dry weight pasta'),
('spaghetti', 'carb', 80, 'grams', 'Dry weight spaghetti'),
('noodles', 'carb', 80, 'grams', 'Dry weight noodles'),
('bread', 'carb', 60, 'grams', 'About 2 slices'),
('quinoa', 'carb', 60, 'grams', 'Dry weight quinoa'),
('couscous', 'carb', 60, 'grams', 'Dry weight couscous'),

-- Dairy
('milk', 'dairy', 250, 'ml', 'One cup of milk'),
('yogurt', 'dairy', 150, 'grams', 'Individual serving'),
('cheese', 'dairy', 30, 'grams', 'Sliced or grated cheese'),
('butter', 'dairy', 10, 'grams', 'About 1 tbsp'),
('cream', 'dairy', 50, 'ml', 'Heavy/cooking cream'),
('paneer', 'dairy', 75, 'grams', 'Indian cottage cheese'),

-- Legumes
('lentils', 'protein', 60, 'grams', 'Dry weight lentils'),
('chickpeas', 'protein', 60, 'grams', 'Dry weight chickpeas'),
('black_beans', 'protein', 60, 'grams', 'Dry weight beans'),
('kidney_beans', 'protein', 60, 'grams', 'Dry weight beans')
ON CONFLICT (ingredient_name) DO NOTHING;

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_standard_serving_ingredient ON standard_serving_sizes(ingredient_name);
CREATE INDEX IF NOT EXISTS idx_standard_serving_category ON standard_serving_sizes(category);

-- ============================================================================
-- SECTION 4: Helper Functions for Quantity Operations
-- ============================================================================

-- Function to convert between units (simplified - full logic in application layer)
CREATE OR REPLACE FUNCTION convert_unit(
    quantity DECIMAL(10,2),
    from_unit VARCHAR(50),
    to_unit VARCHAR(50)
) RETURNS DECIMAL(10,2) AS $$
DECLARE
    from_factor DECIMAL(10,6);
    to_factor DECIMAL(10,6);
    from_category VARCHAR(20);
    to_category VARCHAR(20);
    result DECIMAL(10,2);
BEGIN
    -- Get conversion factors and categories
    SELECT conversion_factor, category INTO from_factor, from_category
    FROM quantity_units WHERE unit_name = from_unit;
    
    SELECT conversion_factor, category INTO to_factor, to_category
    FROM quantity_units WHERE unit_name = to_unit;
    
    -- Check if units are in same category
    IF from_category != to_category THEN
        RAISE EXCEPTION 'Cannot convert between different categories: % and %', from_category, to_category;
    END IF;
    
    -- Convert to base unit, then to target unit
    result := quantity * from_factor / to_factor;
    
    RETURN result;
END;
$$ LANGUAGE plpgsql;

-- Function to get standard serving size for an ingredient
CREATE OR REPLACE FUNCTION get_standard_serving(
    ingredient VARCHAR(255),
    num_servings INTEGER DEFAULT 1
) RETURNS TABLE(quantity DECIMAL(10,2), unit VARCHAR(50)) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        (serving_size * num_servings)::DECIMAL(10,2) as quantity,
        standard_serving_sizes.unit
    FROM standard_serving_sizes
    WHERE ingredient_name = ingredient
    LIMIT 1;
END;
$$ LANGUAGE plpgsql;

-- Function to check pantry sufficiency for a recipe
CREATE OR REPLACE FUNCTION check_recipe_sufficiency(
    p_user_id UUID,
    p_recipe_id UUID,
    p_servings INTEGER
) RETURNS TABLE(
    ingredient_name VARCHAR(255),
    required_quantity DECIMAL(10,2),
    required_unit VARCHAR(50),
    available_quantity DECIMAL(10,2),
    available_unit VARCHAR(50),
    sufficient BOOLEAN,
    shortage DECIMAL(10,2)
) AS $$
BEGIN
    RETURN QUERY
    WITH recipe_needs AS (
        SELECT 
            ri.ingredient_name,
            (ri.quantity * p_servings / r.servings)::DECIMAL(10,2) as needed_qty,
            ri.unit as needed_unit
        FROM recipes r
        JOIN recipe_ingredients ri ON r.id = ri.recipe_id
        WHERE r.id = p_recipe_id
    ),
    pantry_available AS (
        SELECT 
            up.ingredient_name,
            up.quantity,
            up.unit
        FROM user_pantry up
        WHERE up.user_id = p_user_id 
        AND up.status = 'available'
    )
    SELECT 
        rn.ingredient_name,
        rn.needed_qty as required_quantity,
        rn.needed_unit as required_unit,
        COALESCE(pa.quantity, 0)::DECIMAL(10,2) as available_quantity,
        COALESCE(pa.unit, rn.needed_unit) as available_unit,
        (COALESCE(pa.quantity, 0) >= rn.needed_qty) as sufficient,
        GREATEST(0, rn.needed_qty - COALESCE(pa.quantity, 0))::DECIMAL(10,2) as shortage
    FROM recipe_needs rn
    LEFT JOIN pantry_available pa ON rn.ingredient_name = pa.ingredient_name;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- SECTION 5: Update Existing Triggers to Handle Quantities
-- ============================================================================

-- Update auto_add_to_pantry trigger to include quantities
CREATE OR REPLACE FUNCTION auto_add_confirmed_to_pantry()
RETURNS TRIGGER AS $$
BEGIN
    -- Only proceed if ingredient is confirmed
    IF NEW.confirmation_status = 'confirmed' THEN
        -- Check if ingredient already exists in user's pantry
        IF EXISTS (
            SELECT 1 FROM user_pantry 
            WHERE user_id = NEW.user_id 
            AND ingredient_name = NEW.canonical_name
            AND status = 'available'
        ) THEN
            -- Update existing quantity (add to existing)
            UPDATE user_pantry
            SET 
                quantity = COALESCE(quantity, 0) + COALESCE(NEW.detected_quantity, 0),
                unit = COALESCE(NEW.detected_unit, unit),
                updated_at = NOW()
            WHERE user_id = NEW.user_id 
            AND ingredient_name = NEW.canonical_name
            AND status = 'available';
        ELSE
            -- Insert new pantry item with quantity
            INSERT INTO user_pantry (
                user_id,
                scan_id,
                ingredient_name,
                display_name,
                quantity,
                unit,
                estimated,
                confidence,
                source,
                status
            ) VALUES (
                NEW.user_id,
                NEW.scan_id,
                NEW.canonical_name,
                NEW.detected_name,
                NEW.detected_quantity,
                NEW.detected_unit,
                true,  -- Estimated from scan
                NEW.quantity_confidence,
                'scan',
                'available'
            );
        END IF;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Recreate trigger (drop and create to ensure it uses updated function)
DROP TRIGGER IF EXISTS auto_add_to_pantry_trigger ON detected_ingredients;
CREATE TRIGGER auto_add_to_pantry_trigger
    AFTER UPDATE OF confirmation_status ON detected_ingredients
    FOR EACH ROW
    WHEN (NEW.confirmation_status = 'confirmed')
    EXECUTE FUNCTION auto_add_confirmed_to_pantry();

-- ============================================================================
-- SECTION 6: Create Materialized View for Pantry Inventory Summary
-- ============================================================================

CREATE MATERIALIZED VIEW IF NOT EXISTS pantry_inventory_summary AS
SELECT 
    user_id,
    COUNT(*) as total_items,
    COUNT(*) FILTER (WHERE quantity IS NOT NULL) as items_with_quantity,
    COUNT(*) FILTER (WHERE quantity IS NULL) as items_without_quantity,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE quantity IS NOT NULL) / NULLIF(COUNT(*), 0),
        2
    ) as quantity_completeness_pct,
    COUNT(*) FILTER (WHERE estimated = true) as estimated_items,
    COUNT(*) FILTER (WHERE estimated = false) as user_entered_items,
    SUM(CASE WHEN unit = 'grams' THEN quantity ELSE 0 END) as total_grams,
    SUM(CASE WHEN unit = 'ml' THEN quantity ELSE 0 END) as total_ml,
    COUNT(*) FILTER (WHERE status = 'available') as available_items,
    COUNT(*) FILTER (WHERE status = 'low') as low_items
FROM user_pantry
GROUP BY user_id;

-- Create index
CREATE UNIQUE INDEX idx_pantry_summary_user ON pantry_inventory_summary(user_id);

-- Add comment
COMMENT ON MATERIALIZED VIEW pantry_inventory_summary IS 'Summary statistics for user pantry inventory with quantity tracking';

-- Function to refresh pantry summary
CREATE OR REPLACE FUNCTION refresh_pantry_summary()
RETURNS VOID AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY pantry_inventory_summary;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- SECTION 7: RLS Policies for New Tables
-- ============================================================================

-- Enable RLS on new tables
ALTER TABLE quantity_units ENABLE ROW LEVEL SECURITY;
ALTER TABLE standard_serving_sizes ENABLE ROW LEVEL SECURITY;

-- Allow public read access to reference tables
CREATE POLICY "Allow public read access to quantity_units"
    ON quantity_units FOR SELECT
    USING (true);

CREATE POLICY "Allow public read access to standard_serving_sizes"
    ON standard_serving_sizes FOR SELECT
    USING (true);

-- ============================================================================
-- SECTION 8: Update Existing Data (Optional - Set Defaults)
-- ============================================================================

-- Set default quantity for existing pantry items without quantities
-- (Leave NULL for now - users will update via UI)
-- UPDATE user_pantry SET quantity = NULL, unit = NULL WHERE quantity IS NULL;

-- ============================================================================
-- SECTION 9: Validation Constraints
-- ============================================================================

-- Add check constraints
ALTER TABLE user_pantry
ADD CONSTRAINT check_quantity_positive CHECK (quantity IS NULL OR quantity > 0),
ADD CONSTRAINT check_confidence_range CHECK (quantity_confidence IS NULL OR (quantity_confidence >= 0 AND quantity_confidence <= 1));

ALTER TABLE detected_ingredients
ADD CONSTRAINT check_detected_quantity_positive CHECK (detected_quantity IS NULL OR detected_quantity > 0),
ADD CONSTRAINT check_detected_confidence_range CHECK (quantity_confidence IS NULL OR (quantity_confidence >= 0 AND quantity_confidence <= 1));

ALTER TABLE standard_serving_sizes
ADD CONSTRAINT check_serving_positive CHECK (serving_size > 0);

-- ============================================================================
-- SECTION 10: Create Indexes for Performance
-- ============================================================================

-- Indexes for quantity-based queries
CREATE INDEX idx_user_pantry_quantity ON user_pantry(quantity) WHERE quantity IS NOT NULL;
CREATE INDEX idx_user_pantry_unit ON user_pantry(unit) WHERE unit IS NOT NULL;
CREATE INDEX idx_user_pantry_estimated ON user_pantry(estimated);

-- Composite index for quantity filtering
CREATE INDEX idx_user_pantry_user_qty ON user_pantry(user_id, status) WHERE quantity IS NOT NULL;

-- ============================================================================
-- Migration Complete
-- ============================================================================

-- Summary
DO $$
BEGIN
    RAISE NOTICE '======================================';
    RAISE NOTICE 'Migration 003 Complete!';
    RAISE NOTICE '======================================';
    RAISE NOTICE 'Added:';
    RAISE NOTICE '- Quantity columns to user_pantry and detected_ingredients';
    RAISE NOTICE '- quantity_units reference table (21 units)';
    RAISE NOTICE '- standard_serving_sizes table (50+ ingredients)';
    RAISE NOTICE '- Helper functions: convert_unit, get_standard_serving, check_recipe_sufficiency';
    RAISE NOTICE '- Updated triggers to handle quantities';
    RAISE NOTICE '- Materialized view: pantry_inventory_summary';
    RAISE NOTICE '- RLS policies for new tables';
    RAISE NOTICE '======================================';
END $$;
