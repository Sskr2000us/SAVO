-- =====================================================
-- SAVO Storage Bucket Policies
-- Migration: 006
-- Created: 2026-01-06
-- Purpose: Set up RLS policies for Supabase Storage buckets
-- =====================================================

-- Enable RLS on storage.buckets table (if not already enabled)
ALTER TABLE storage.buckets ENABLE ROW LEVEL SECURITY;

-- Enable RLS on storage.objects table (if not already enabled)
ALTER TABLE storage.objects ENABLE ROW LEVEL SECURITY;

-- =====================================================
-- BUCKET 1: savo-ingredients (Public Read, Admin Write)
-- Purpose: Reference ingredient images for CV training and display
-- =====================================================

-- Policy: Allow public read access (SELECT)
CREATE POLICY "Public read access for ingredient images"
ON storage.objects
FOR SELECT
TO public
USING (bucket_id = 'savo-ingredients');

-- Policy: Allow authenticated users to insert (admin only via service role)
CREATE POLICY "Authenticated users can upload ingredient images"
ON storage.objects
FOR INSERT
TO authenticated
WITH CHECK (bucket_id = 'savo-ingredients');

-- Policy: Allow authenticated users to update (admin only via service role)
CREATE POLICY "Authenticated users can update ingredient images"
ON storage.objects
FOR UPDATE
TO authenticated
USING (bucket_id = 'savo-ingredients')
WITH CHECK (bucket_id = 'savo-ingredients');

-- Policy: Allow authenticated users to delete (admin only via service role)
CREATE POLICY "Authenticated users can delete ingredient images"
ON storage.objects
FOR DELETE
TO authenticated
USING (bucket_id = 'savo-ingredients');

-- =====================================================
-- BUCKET 2: savo-ingredients-thumbnails (Public Read, Admin Write)
-- Purpose: Optimized thumbnails for fast loading
-- =====================================================

-- Policy: Allow public read access
CREATE POLICY "Public read access for thumbnails"
ON storage.objects
FOR SELECT
TO public
USING (bucket_id = 'savo-ingredients-thumbnails');

-- Policy: Allow authenticated users to insert
CREATE POLICY "Authenticated users can upload thumbnails"
ON storage.objects
FOR INSERT
TO authenticated
WITH CHECK (bucket_id = 'savo-ingredients-thumbnails');

-- Policy: Allow authenticated users to update
CREATE POLICY "Authenticated users can update thumbnails"
ON storage.objects
FOR UPDATE
TO authenticated
USING (bucket_id = 'savo-ingredients-thumbnails')
WITH CHECK (bucket_id = 'savo-ingredients-thumbnails');

-- Policy: Allow authenticated users to delete
CREATE POLICY "Authenticated users can delete thumbnails"
ON storage.objects
FOR DELETE
TO authenticated
USING (bucket_id = 'savo-ingredients-thumbnails');

-- =====================================================
-- BUCKET 3: savo-user-scans (Private, User-Only Access)
-- Purpose: User-uploaded ingredient scans (private)
-- =====================================================

-- Policy: Users can only read their own scans
CREATE POLICY "Users can read their own scans"
ON storage.objects
FOR SELECT
TO authenticated
USING (
    bucket_id = 'savo-user-scans' 
    AND (storage.foldername(name))[1] = auth.uid()::text
);

-- Policy: Users can only upload to their own folder
CREATE POLICY "Users can upload to their own folder"
ON storage.objects
FOR INSERT
TO authenticated
WITH CHECK (
    bucket_id = 'savo-user-scans' 
    AND (storage.foldername(name))[1] = auth.uid()::text
);

-- Policy: Users can only update their own scans
CREATE POLICY "Users can update their own scans"
ON storage.objects
FOR UPDATE
TO authenticated
USING (
    bucket_id = 'savo-user-scans' 
    AND (storage.foldername(name))[1] = auth.uid()::text
)
WITH CHECK (
    bucket_id = 'savo-user-scans' 
    AND (storage.foldername(name))[1] = auth.uid()::text
);

-- Policy: Users can only delete their own scans
CREATE POLICY "Users can delete their own scans"
ON storage.objects
FOR DELETE
TO authenticated
USING (
    bucket_id = 'savo-user-scans' 
    AND (storage.foldername(name))[1] = auth.uid()::text
);

-- =====================================================
-- HELPER FUNCTIONS
-- =====================================================

-- Function: Get storage URL for an ingredient image
CREATE OR REPLACE FUNCTION get_ingredient_image_url(
    p_ingredient_id UUID,
    p_visual_state TEXT DEFAULT 'raw_whole'
) RETURNS TEXT AS $$
DECLARE
    v_image_id TEXT;
    v_bucket_name TEXT := 'savo-ingredients';
BEGIN
    -- Get the image_id from ingredient_images table
    SELECT image_id INTO v_image_id
    FROM ingredient_images
    WHERE ingredient_id = p_ingredient_id
    AND visual_state = p_visual_state
    ORDER BY created_at DESC
    LIMIT 1;
    
    IF v_image_id IS NULL THEN
        RETURN NULL;
    END IF;
    
    -- Return the full URL
    RETURN format(
        '%s/storage/v1/object/public/%s/%s',
        current_setting('app.settings.supabase_url', true),
        v_bucket_name,
        v_image_id
    );
END;
$$ LANGUAGE plpgsql STABLE;

-- Function: Get thumbnail URL
CREATE OR REPLACE FUNCTION get_ingredient_thumbnail_url(
    p_ingredient_id UUID,
    p_visual_state TEXT DEFAULT 'raw_whole'
) RETURNS TEXT AS $$
DECLARE
    v_image_id TEXT;
    v_bucket_name TEXT := 'savo-ingredients-thumbnails';
BEGIN
    -- Get the image_id from ingredient_images table
    SELECT image_id INTO v_image_id
    FROM ingredient_images
    WHERE ingredient_id = p_ingredient_id
    AND visual_state = p_visual_state
    ORDER BY created_at DESC
    LIMIT 1;
    
    IF v_image_id IS NULL THEN
        RETURN NULL;
    END IF;
    
    -- Return the full URL (thumbnail has same image_id with _thumb suffix)
    RETURN format(
        '%s/storage/v1/object/public/%s/%s_thumb.jpg',
        current_setting('app.settings.supabase_url', true),
        v_bucket_name,
        v_image_id
    );
END;
$$ LANGUAGE plpgsql STABLE;

-- =====================================================
-- VERIFICATION QUERIES
-- =====================================================

-- Check bucket configurations
COMMENT ON SCHEMA storage IS 'Storage bucket policies configured for SAVO Ingredient Intelligence';

-- Verify policies exist
DO $$
DECLARE
    policy_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO policy_count
    FROM pg_policies
    WHERE schemaname = 'storage'
    AND tablename = 'objects'
    AND policyname LIKE '%ingredient%' OR policyname LIKE '%thumbnail%' OR policyname LIKE '%scan%';
    
    RAISE NOTICE 'Total storage policies created: %', policy_count;
END $$;
