-- =====================================================
-- Migration 006b: Storage RLS Policies Only
-- =====================================================
-- PREREQUISITE: Create buckets manually via Supabase Dashboard first:
--   1. savo-ingredients (public: true)
--   2. savo-ingredients-thumbnails (public: true)
--   3. savo-user-scans (public: false)
--
-- Then run this SQL file to apply RLS policies
-- =====================================================
-- NOTE: RLS is already enabled on storage.objects by default in Supabase
-- We just need to add the policies
-- =====================================================

-- ===== POLICIES FOR: savo-ingredients (PUBLIC READ) =====

-- Drop existing policies if they exist (for idempotency)
DROP POLICY IF EXISTS "Public can view ingredient images" ON storage.objects;
DROP POLICY IF EXISTS "Authenticated users can upload ingredient images" ON storage.objects;
DROP POLICY IF EXISTS "Authenticated users can update ingredient images" ON storage.objects;
DROP POLICY IF EXISTS "Authenticated users can delete ingredient images" ON storage.objects;

-- Allow public to view ingredient images
CREATE POLICY "Public can view ingredient images"
ON storage.objects FOR SELECT
USING (bucket_id = 'savo-ingredients');

-- Allow authenticated users to upload ingredient images
CREATE POLICY "Authenticated users can upload ingredient images"
ON storage.objects FOR INSERT
WITH CHECK (
  bucket_id = 'savo-ingredients' 
  AND auth.role() = 'authenticated'
);

-- Allow authenticated users to update ingredient images
CREATE POLICY "Authenticated users can update ingredient images"
ON storage.objects FOR UPDATE
USING (
  bucket_id = 'savo-ingredients'
  AND auth.role() = 'authenticated'
);

-- Allow authenticated users to delete ingredient images
CREATE POLICY "Authenticated users can delete ingredient images"
ON storage.objects FOR DELETE
USING (
  bucket_id = 'savo-ingredients'
  AND auth.role() = 'authenticated'
);

-- ===== POLICIES FOR: savo-ingredients-thumbnails (PUBLIC READ) =====

-- Drop existing policies if they exist (for idempotency)
DROP POLICY IF EXISTS "Public can view ingredient thumbnails" ON storage.objects;
DROP POLICY IF EXISTS "Authenticated users can upload thumbnails" ON storage.objects;
DROP POLICY IF EXISTS "Authenticated users can update thumbnails" ON storage.objects;
DROP POLICY IF EXISTS "Authenticated users can delete thumbnails" ON storage.objects;

-- Allow public to view ingredient thumbnails
CREATE POLICY "Public can view ingredient thumbnails"
ON storage.objects FOR SELECT
USING (bucket_id = 'savo-ingredients-thumbnails');

-- Allow authenticated users to upload thumbnails
CREATE POLICY "Authenticated users can upload thumbnails"
ON storage.objects FOR INSERT
WITH CHECK (
  bucket_id = 'savo-ingredients-thumbnails'
  AND auth.role() = 'authenticated'
);

-- Allow authenticated users to update thumbnails
CREATE POLICY "Authenticated users can update thumbnails"
ON storage.objects FOR UPDATE
USING (
  bucket_id = 'savo-ingredients-thumbnails'
  AND auth.role() = 'authenticated'
);

-- Allow authenticated users to delete thumbnails
CREATE POLICY "Authenticated users can delete thumbnails"
ON storage.objects FOR DELETE
USING (
  bucket_id = 'savo-ingredients-thumbnails'
  AND auth.role() = 'authenticated'
);

-- ===== POLICIES FOR: savo-user-scans (PRIVATE - USER ONLY) =====

-- Drop existing policies if they exist (for idempotency)
DROP POLICY IF EXISTS "Users can view their own scans" ON storage.objects;
DROP POLICY IF EXISTS "Users can upload their own scans" ON storage.objects;
DROP POLICY IF EXISTS "Users can update their own scans" ON storage.objects;
DROP POLICY IF EXISTS "Users can delete their own scans" ON storage.objects;

-- Users can only view their own scans (using folder-based isolation)
CREATE POLICY "Users can view their own scans"
ON storage.objects FOR SELECT
USING (
  bucket_id = 'savo-user-scans'
  AND (storage.foldername(name))[1] = auth.uid()::text
);

-- Users can only upload their own scans (using folder-based isolation)
CREATE POLICY "Users can upload their own scans"
ON storage.objects FOR INSERT
WITH CHECK (
  bucket_id = 'savo-user-scans'
  AND (storage.foldername(name))[1] = auth.uid()::text
);

-- Users can only update their own scans (using folder-based isolation)
CREATE POLICY "Users can update their own scans"
ON storage.objects FOR UPDATE
USING (
  bucket_id = 'savo-user-scans'
  AND (storage.foldername(name))[1] = auth.uid()::text
);

-- Users can only delete their own scans (using folder-based isolation)
CREATE POLICY "Users can delete their own scans"
ON storage.objects FOR DELETE
USING (
  bucket_id = 'savo-user-scans'
  AND (storage.foldername(name))[1] = auth.uid()::text
);

-- ===== HELPER FUNCTIONS =====

-- Function to get public URL for ingredient image
CREATE OR REPLACE FUNCTION get_ingredient_image_url(image_id TEXT)
RETURNS TEXT AS $$
DECLARE
  base_url TEXT;
BEGIN
  -- Get Supabase project URL
  base_url := current_setting('app.settings.supabase_url', true);
  
  IF base_url IS NULL THEN
    base_url := 'https://your-project.supabase.co';
  END IF;
  
  RETURN base_url || '/storage/v1/object/public/savo-ingredients/' || image_id;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Function to get public URL for thumbnail
CREATE OR REPLACE FUNCTION get_ingredient_thumbnail_url(image_id TEXT)
RETURNS TEXT AS $$
DECLARE
  base_url TEXT;
BEGIN
  base_url := current_setting('app.settings.supabase_url', true);
  
  IF base_url IS NULL THEN
    base_url := 'https://your-project.supabase.co';
  END IF;
  
  RETURN base_url || '/storage/v1/object/public/savo-ingredients-thumbnails/' || image_id;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- ===== VERIFICATION QUERIES =====

-- Check which buckets exist (informational only)
SELECT id, name, public, file_size_limit, allowed_mime_types
FROM storage.buckets 
WHERE id IN ('savo-ingredients', 'savo-ingredients-thumbnails', 'savo-user-scans')
ORDER BY id;

-- List all policies created
SELECT 
  schemaname,
  tablename,
  policyname,
  permissive,
  roles,
  cmd
FROM pg_policies 
WHERE tablename = 'objects' 
  AND schemaname = 'storage'
ORDER BY policyname;

-- Expected result: 12 policies (4 per bucket: SELECT, INSERT, UPDATE, DELETE)
