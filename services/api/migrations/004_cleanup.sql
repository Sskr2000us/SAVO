-- Cleanup script for migration 004
-- Run this to completely reset the advanced scanning tables

-- Drop all functions first
DROP FUNCTION IF EXISTS search_ingredients_multilang(TEXT, TEXT, INTEGER);
DROP FUNCTION IF EXISTS get_ingredient_by_barcode(TEXT);
DROP FUNCTION IF EXISTS estimate_quantity_from_volume(TEXT, NUMERIC, TEXT);

-- Drop all new tables in reverse dependency order
DROP TABLE IF EXISTS public.barcode_scans CASCADE;
DROP TABLE IF EXISTS public.container_scans CASCADE;
DROP TABLE IF EXISTS public.quantity_calibrations CASCADE;
DROP TABLE IF EXISTS public.ingredient_densities CASCADE;
DROP TABLE IF EXISTS public.reference_objects CASCADE;
DROP TABLE IF EXISTS public.product_barcodes CASCADE;
DROP TABLE IF EXISTS public.master_ingredients CASCADE;

-- Also drop tables without schema prefix (your temporary tables)
DROP TABLE IF EXISTS barcode_scans CASCADE;
DROP TABLE IF EXISTS container_scans CASCADE;
DROP TABLE IF EXISTS quantity_calibrations CASCADE;
DROP TABLE IF EXISTS ingredient_densities CASCADE;
DROP TABLE IF EXISTS reference_objects CASCADE;
DROP TABLE IF EXISTS product_barcodes CASCADE;
DROP TABLE IF EXISTS master_ingredients CASCADE;

-- Remove columns added to inventory_items
ALTER TABLE public.inventory_items 
DROP COLUMN IF EXISTS days_until_expiry CASCADE;

ALTER TABLE public.inventory_items
DROP COLUMN IF EXISTS expiry_date CASCADE,
DROP COLUMN IF EXISTS purchase_date CASCADE,
DROP COLUMN IF EXISTS barcode CASCADE;

-- Print success message
DO $$
BEGIN
    RAISE NOTICE 'Cleanup complete. Now run migration 004_global_ingredients_and_barcode.sql';
END $$;
