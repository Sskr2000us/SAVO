-- Storage bucket + RLS policies for scan videos (idempotent)
-- Date: 2026-01-11
-- Bucket: scan-videos (private)

BEGIN;

-- Create bucket if missing
INSERT INTO storage.buckets (id, name, public)
SELECT 'scan-videos', 'scan-videos', false
WHERE NOT EXISTS (SELECT 1 FROM storage.buckets WHERE id = 'scan-videos');

-- Policies (do not drop other policies)
DROP POLICY IF EXISTS "Users can read their own scan videos" ON storage.objects;
DROP POLICY IF EXISTS "Users can upload their own scan videos" ON storage.objects;
DROP POLICY IF EXISTS "Users can update their own scan videos" ON storage.objects;
DROP POLICY IF EXISTS "Users can delete their own scan videos" ON storage.objects;

CREATE POLICY "Users can read their own scan videos"
ON storage.objects
FOR SELECT
TO authenticated
USING (
    bucket_id = 'scan-videos'
    AND (storage.foldername(name))[1] = auth.uid()::text
);

CREATE POLICY "Users can upload their own scan videos"
ON storage.objects
FOR INSERT
TO authenticated
WITH CHECK (
    bucket_id = 'scan-videos'
    AND (storage.foldername(name))[1] = auth.uid()::text
);

CREATE POLICY "Users can update their own scan videos"
ON storage.objects
FOR UPDATE
TO authenticated
USING (
    bucket_id = 'scan-videos'
    AND (storage.foldername(name))[1] = auth.uid()::text
)
WITH CHECK (
    bucket_id = 'scan-videos'
    AND (storage.foldername(name))[1] = auth.uid()::text
);

CREATE POLICY "Users can delete their own scan videos"
ON storage.objects
FOR DELETE
TO authenticated
USING (
    bucket_id = 'scan-videos'
    AND (storage.foldername(name))[1] = auth.uid()::text
);

COMMIT;
