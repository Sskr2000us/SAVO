-- Add Visual Confirmation for Scanned Ingredients
-- Date: 2026-01-06
-- Purpose: Store ingredient thumbnails and images for visual verification

-- ============================================================================
-- 1. Add image fields to detected_ingredients table
-- ============================================================================
ALTER TABLE public.detected_ingredients
ADD COLUMN IF NOT EXISTS thumbnail_url TEXT,
ADD COLUMN IF NOT EXISTS full_image_url TEXT;

COMMENT ON COLUMN public.detected_ingredients.thumbnail_url IS 'Cropped thumbnail of detected ingredient using bbox';
COMMENT ON COLUMN public.detected_ingredients.full_image_url IS 'Full scan image URL for reference';

-- ============================================================================
-- 2. Add image_url to inventory_items for visual reference
-- ============================================================================
ALTER TABLE public.inventory_items
ADD COLUMN IF NOT EXISTS image_url TEXT,
ADD COLUMN IF NOT EXISTS image_source TEXT CHECK (image_source IN ('scan', 'receipt', 'manual', 'default'));

COMMENT ON COLUMN public.inventory_items.image_url IS 'Visual reference image for this ingredient';
COMMENT ON COLUMN public.inventory_items.image_source IS 'Source of the image: scan/receipt/manual/default';

-- ============================================================================
-- 3. Add image_url to user_pantry for visual inventory display
-- ============================================================================
ALTER TABLE public.user_pantry
ADD COLUMN IF NOT EXISTS image_url TEXT,
ADD COLUMN IF NOT EXISTS image_confidence NUMERIC(3,2) CHECK (image_confidence >= 0 AND image_confidence <= 1);

COMMENT ON COLUMN public.user_pantry.image_url IS 'Visual reference of the ingredient';
COMMENT ON COLUMN public.user_pantry.image_confidence IS 'Confidence that image matches the ingredient';

-- ============================================================================
-- 4. Create index for faster image lookups
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_detected_ingredients_thumbnail 
ON public.detected_ingredients(thumbnail_url) 
WHERE thumbnail_url IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_inventory_items_image 
ON public.inventory_items(image_url) 
WHERE image_url IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_user_pantry_image 
ON public.user_pantry(image_url) 
WHERE image_url IS NOT NULL;

-- ============================================================================
-- 5. Create view for inventory with images
-- ============================================================================
CREATE OR REPLACE VIEW public.inventory_with_images AS
SELECT 
    ii.*,
    COALESCE(ii.image_url, up.image_url) as display_image_url,
    CASE 
        WHEN ii.image_url IS NOT NULL THEN 'inventory'
        WHEN up.image_url IS NOT NULL THEN 'pantry'
        ELSE 'none'
    END as image_source_type
FROM public.inventory_items ii
LEFT JOIN public.user_pantry up ON ii.canonical_name = up.ingredient_name AND ii.user_id = up.user_id
WHERE ii.is_current = true;

COMMENT ON VIEW public.inventory_with_images IS 'Inventory items with best available image URL';

-- ============================================================================
-- 6. Function to copy thumbnail to inventory when ingredient is confirmed
-- ============================================================================
CREATE OR REPLACE FUNCTION copy_thumbnail_to_inventory()
RETURNS TRIGGER AS $$
BEGIN
    -- When a detected ingredient is confirmed, copy its thumbnail to inventory
    IF NEW.confirmation_status = 'confirmed' AND NEW.thumbnail_url IS NOT NULL THEN
        UPDATE public.inventory_items
        SET 
            image_url = NEW.thumbnail_url,
            image_source = 'scan'
        WHERE user_id = (
            SELECT user_id FROM public.ingredient_scans WHERE id = NEW.scan_id
        )
        AND canonical_name = COALESCE(NEW.canonical_name, NEW.detected_name)
        AND image_url IS NULL;  -- Only update if no image exists
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger
DROP TRIGGER IF EXISTS trg_copy_thumbnail_to_inventory ON public.detected_ingredients;
CREATE TRIGGER trg_copy_thumbnail_to_inventory
    AFTER UPDATE OF confirmation_status ON public.detected_ingredients
    FOR EACH ROW
    EXECUTE FUNCTION copy_thumbnail_to_inventory();

-- ============================================================================
-- 7. Function to copy thumbnail to user_pantry when added
-- ============================================================================
CREATE OR REPLACE FUNCTION copy_thumbnail_to_pantry()
RETURNS TRIGGER AS $$
DECLARE
    v_thumbnail TEXT;
BEGIN
    -- Try to get thumbnail from most recent confirmed detection
    SELECT thumbnail_url INTO v_thumbnail
    FROM public.detected_ingredients di
    JOIN public.ingredient_scans isc ON di.scan_id = isc.id
    WHERE isc.user_id = NEW.user_id
        AND (di.canonical_name = NEW.ingredient_name OR di.detected_name = NEW.ingredient_name)
        AND di.confirmation_status = 'confirmed'
        AND di.thumbnail_url IS NOT NULL
    ORDER BY isc.created_at DESC
    LIMIT 1;
    
    IF v_thumbnail IS NOT NULL AND NEW.image_url IS NULL THEN
        NEW.image_url := v_thumbnail;
        NEW.image_confidence := 0.95;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger
DROP TRIGGER IF EXISTS trg_copy_thumbnail_to_pantry ON public.user_pantry;
CREATE TRIGGER trg_copy_thumbnail_to_pantry
    BEFORE INSERT ON public.user_pantry
    FOR EACH ROW
    EXECUTE FUNCTION copy_thumbnail_to_pantry();

-- ============================================================================
-- 8. Add receipt items table for receipt image storage
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.receipt_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    receipt_scan_id UUID REFERENCES public.receipt_scans(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    
    -- Item details
    item_name TEXT NOT NULL,
    canonical_name TEXT,
    quantity NUMERIC,
    unit TEXT,
    price NUMERIC(10,2),
    
    -- Visual reference
    thumbnail_url TEXT,  -- Cropped image of this line item
    bbox JSONB,  -- Bounding box in receipt image
    
    -- Metadata
    line_number INTEGER,
    confidence NUMERIC(3,2),
    added_to_inventory BOOLEAN DEFAULT false,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_receipt_items_receipt ON public.receipt_items(receipt_scan_id);
CREATE INDEX idx_receipt_items_user ON public.receipt_items(user_id);
CREATE INDEX idx_receipt_items_thumbnail ON public.receipt_items(thumbnail_url) WHERE thumbnail_url IS NOT NULL;

COMMENT ON TABLE public.receipt_items IS 'Individual items extracted from receipt scans with images';

-- Enable RLS
ALTER TABLE public.receipt_items ENABLE ROW LEVEL SECURITY;

CREATE POLICY receipt_items_user_policy ON public.receipt_items
    FOR ALL USING (auth.uid() = user_id);

-- ============================================================================
-- 9. Update receipt_scans to track processed items count
-- ============================================================================
ALTER TABLE public.receipt_scans
ADD COLUMN IF NOT EXISTS items_count INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS items_with_images INTEGER DEFAULT 0;

COMMENT ON COLUMN public.receipt_scans.items_count IS 'Total number of items detected';
COMMENT ON COLUMN public.receipt_scans.items_with_images IS 'Number of items with thumbnail images';
