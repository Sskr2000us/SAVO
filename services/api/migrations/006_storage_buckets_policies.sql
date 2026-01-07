-- =====================================================
-- SAVO Storage Bucket Policies
-- Migration: 006
-- Created: 2026-01-06
-- Purpose: Set up RLS policies for Supabase Storage buckets
-- =====================================================
-- PREREQUISITE: Create these 3 buckets via Supabase Dashboard first:
--   1. savo-ingredients (public: YES, size: 10MB)
--   2. savo-ingredients-thumbnails (public: YES, size: 1MB)  
--   3. savo-user-scans (public: NO, size: 10MB)
-- =====================================================
-- NOTE: RLS is already enabled on storage.objects by default in Supabase
-- No need to manually enable it
-- =====================================================

-- =====================================================
-- CLEANUP: Drop existing policies if they exist (idempotent)
-- =====================================================

DROP POLICY IF EXISTS "Public read access for ingredient images" ON storage.objects;
DROP POLICY IF EXISTS "Authenticated users can upload ingredient images" ON storage.objects;
DROP POLICY IF EXISTS "Authenticated users can update ingredient images" ON storage.objects;
DROP POLICY IF EXISTS "Authenticated users can delete ingredient images" ON storage.objects;

DROP POLICY IF EXISTS "Public read access for thumbnails" ON storage.objects;
DROP POLICY IF EXISTS "Authenticated users can upload thumbnails" ON storage.objects;
DROP POLICY IF EXISTS "Authenticated users can update thumbnails" ON storage.objects;
DROP POLICY IF EXISTS "Authenticated users can delete thumbnails" ON storage.objects;

DROP POLICY IF EXISTS "Users can read their own scans" ON storage.objects;
DROP POLICY IF EXISTS "Users can upload to their own folder" ON storage.objects;
DROP POLICY IF EXISTS "Users can update their own scans" ON storage.objects;
DROP POLICY IF EXISTS "Users can delete their own scans" ON storage.objects;

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

-- Verify buckets exist
SELECT id, name, public, file_size_limit
FROM storage.buckets
WHERE name IN ('savo-ingredients', 'savo-ingredients-thumbnails', 'savo-user-scans')
ORDER BY name;

-- Verify policies were created
SELECT 
    policyname,
    cmd as operation,
    CASE 
        WHEN policyname LIKE '%ingredient image%' THEN 'savo-ingredients'
        WHEN policyname LIKE '%thumbnail%' THEN 'savo-ingredients-thumbnails'
        WHEN policyname LIKE '%scan%' THEN 'savo-user-scans'
        ELSE 'unknown'
    END as bucket
FROM pg_policies 
WHERE schemaname = 'storage'
    AND tablename = 'objects'
    AND policyname IN (
        'Public read access for ingredient images',
        'Authenticated users can upload ingredient images',
        'Authenticated users can update ingredient images',
        'Authenticated users can delete ingredient images',
        'Public read access for thumbnails',
        'Authenticated users can upload thumbnails',
        'Authenticated users can update thumbnails',
        'Authenticated users can delete thumbnails',
        'Users can read their own scans',
        'Users can upload to their own folder',
        'Users can update their own scans',
        'Users can delete their own scans'
    )
ORDER BY bucket, cmd;
