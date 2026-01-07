# Supabase Storage Bucket Setup Guide

## Overview
This guide walks you through setting up Supabase Storage buckets for the SAVO Ingredient Intelligence System.

## Prerequisites

1. **Supabase Account** with project created
2. **Python 3.8+** installed
3. **Supabase Python SDK** installed
4. **Environment Variables** configured

## Required Environment Variables

```powershell
# Set these in your PowerShell session
$env:SUPABASE_URL = "https://your-project-id.supabase.co"
$env:SUPABASE_SERVICE_ROLE_KEY = "your-service-role-key"
```

### Where to Find These Values

1. **SUPABASE_URL**:
   - Go to https://app.supabase.com
   - Select your project
   - Navigate to **Settings** → **API**
   - Copy the **Project URL**

2. **SUPABASE_SERVICE_ROLE_KEY**:
   - Same location: **Settings** → **API**
   - Copy the **service_role** key (NOT the anon key)
   - ⚠️ **IMPORTANT**: Keep this key secret! It has admin privileges

## Installation Steps

### Step 1: Install Supabase Python SDK

```powershell
# Navigate to your project directory
cd C:\Users\sskr2\SAVO

# Install supabase-py
pip install supabase
```

### Step 2: Create Storage Buckets

```powershell
# Run the Python setup script
python services/api/scripts/setup_storage_buckets.py
```

**Expected Output:**
```
================================================================================
SAVO STORAGE BUCKET SETUP
================================================================================
✅ Connected to Supabase: https://your-project-id.supabase.co

--------------------------------------------------------------------------------
CREATING STORAGE BUCKETS
--------------------------------------------------------------------------------
✅ Created bucket: savo-ingredients
   • Public: True
   • Size limit: 10.0MB
   • Formats: image/jpeg, image/png, image/webp
✅ Created bucket: savo-ingredients-thumbnails
   • Public: True
   • Size limit: 1.0MB
   • Formats: image/jpeg, image/png, image/webp
✅ Created bucket: savo-user-scans
   • Public: False
   • Size limit: 10.0MB
   • Formats: image/jpeg, image/png, image/webp

--------------------------------------------------------------------------------
STORAGE POLICIES
--------------------------------------------------------------------------------
📋 Note: RLS policies need to be set via Supabase Dashboard or SQL

================================================================================
✅ STORAGE SETUP COMPLETE!
================================================================================
```

### Step 3: Apply RLS Policies via SQL

1. **Open Supabase SQL Editor**:
   - Go to https://app.supabase.com
   - Select your project
   - Navigate to **SQL Editor**

2. **Run the Migration Script**:
   - Open `services/api/migrations/006_storage_buckets_policies.sql`
   - Copy the entire content
   - Paste into Supabase SQL Editor
   - Click **Run**

3. **Verify Policies Created**:
   ```sql
   -- Check policies
   SELECT schemaname, tablename, policyname, cmd, roles
   FROM pg_policies
   WHERE schemaname = 'storage'
   AND tablename = 'objects'
   ORDER BY policyname;
   ```

### Step 4: Verify Bucket Configuration

```powershell
# List all buckets
python -c "
from supabase import create_client
import os

supabase = create_client(
    os.getenv('SUPABASE_URL'),
    os.getenv('SUPABASE_SERVICE_ROLE_KEY')
)

buckets = supabase.storage.list_buckets()
for bucket in buckets:
    print(f'✅ {bucket.name} - Public: {bucket.public}')
"
```

## Bucket Structure

### 1. `savo-ingredients` (Public Read)
**Purpose**: Reference ingredient images for CV training and display

**Structure**:
```
savo-ingredients/
├── turmeric/
│   ├── raw_whole.jpg
│   ├── raw_cut.jpg
│   ├── powdered.jpg
│   └── cooked.jpg
├── ginger/
│   ├── raw_whole.jpg
│   ├── raw_cut.jpg
│   └── powdered.jpg
└── tomato/
    ├── raw_whole.jpg
    ├── raw_cut.jpg
    └── cooked.jpg
```

**Access**: Public read, authenticated write

### 2. `savo-ingredients-thumbnails` (Public Read)
**Purpose**: Optimized thumbnails (200x200) for fast loading

**Structure**:
```
savo-ingredients-thumbnails/
├── turmeric/
│   ├── raw_whole_thumb.jpg
│   ├── raw_cut_thumb.jpg
│   ├── powdered_thumb.jpg
│   └── cooked_thumb.jpg
└── ...
```

**Access**: Public read, authenticated write

### 3. `savo-user-scans` (Private)
**Purpose**: User-uploaded ingredient scans

**Structure**:
```
savo-user-scans/
├── {user_id_1}/
│   ├── scan_2026-01-06_123456.jpg
│   └── scan_2026-01-06_234567.jpg
└── {user_id_2}/
    └── scan_2026-01-07_101112.jpg
```

**Access**: User can only access their own folder

## Usage Examples

### Upload Ingredient Image (Python)

```python
from supabase import create_client
import os

# Initialize client
supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
)

# Upload image
with open("turmeric_raw.jpg", "rb") as f:
    response = supabase.storage.from_("savo-ingredients").upload(
        "turmeric/raw_whole.jpg",
        f,
        {
            "content-type": "image/jpeg",
            "cache-control": "3600",
            "upsert": "true"
        }
    )

print(f"✅ Uploaded: {response}")

# Get public URL
url = supabase.storage.from_("savo-ingredients").get_public_url("turmeric/raw_whole.jpg")
print(f"📸 Public URL: {url}")
```

### Upload User Scan (Flutter/Dart)

```dart
import 'package:supabase_flutter/supabase_flutter.dart';

Future<String> uploadUserScan(File imageFile, String userId) async {
  final fileName = 'scan_${DateTime.now().millisecondsSinceEpoch}.jpg';
  final filePath = '$userId/$fileName';
  
  // Upload to user's private folder
  await Supabase.instance.client.storage
    .from('savo-user-scans')
    .upload(filePath, imageFile);
  
  // Get URL (only accessible by this user)
  final url = Supabase.instance.client.storage
    .from('savo-user-scans')
    .getPublicUrl(filePath);
  
  return url;
}
```

### Download Ingredient Image

```python
# Download from public bucket
response = supabase.storage.from_("savo-ingredients").download("turmeric/raw_whole.jpg")

with open("downloaded_turmeric.jpg", "wb") as f:
    f.write(response)
```

## Security & RLS Policies

### Public Buckets (savo-ingredients, savo-ingredients-thumbnails)
- ✅ **SELECT**: Anyone (anon, authenticated)
- 🔒 **INSERT/UPDATE/DELETE**: Authenticated users only (admin via service role)

### Private Bucket (savo-user-scans)
- ✅ **SELECT**: User can read only their own files
- ✅ **INSERT**: User can upload only to their own folder
- ✅ **UPDATE**: User can update only their own files
- ✅ **DELETE**: User can delete only their own files

### Folder Naming Convention
User scans MUST be stored in folders named with the user's UUID:
```
savo-user-scans/{user_uuid}/scan_image.jpg
```

The RLS policy enforces this by checking:
```sql
(storage.foldername(name))[1] = auth.uid()::text
```

## Troubleshooting

### Issue 1: "Bucket already exists"
**Solution**: This is normal if you run the script twice. Buckets are not re-created.

### Issue 2: "Policies not working"
**Solution**: 
1. Check if RLS is enabled on `storage.objects`:
   ```sql
   SELECT tablename, relrowsecurity 
   FROM pg_tables t
   JOIN pg_class c ON t.tablename = c.relname
   WHERE schemaname = 'storage' AND tablename = 'objects';
   ```
2. Verify policies exist:
   ```sql
   SELECT * FROM pg_policies 
   WHERE schemaname = 'storage' AND tablename = 'objects';
   ```

### Issue 3: "403 Forbidden" when uploading
**Solution**:
- For public buckets: Use service role key for uploads
- For user scans: Ensure authenticated and uploading to `{user_id}/filename.jpg`

### Issue 4: "File too large"
**Solution**: 
- Public ingredient images: Max 10MB
- Thumbnails: Max 1MB
- Compress images before upload using Pillow or ImageMagick

## Next Steps

After setting up storage buckets:

1. **Upload Ingredient Images**:
   ```powershell
   python services/api/scripts/upload_ingredient_images.py
   ```

2. **Generate Thumbnails**:
   ```powershell
   python services/api/scripts/generate_thumbnails.py
   ```

3. **Test Image URLs**:
   - Access: `https://your-project-id.supabase.co/storage/v1/object/public/savo-ingredients/turmeric/raw_whole.jpg`

4. **Update Database**:
   - Add `storage_uri` to `ingredient_images` table
   - Link images to ingredients in master_ingredients

## Performance Tips

1. **Use Thumbnails**: Always load thumbnails first, then full images on demand
2. **Enable CDN**: Supabase Storage includes CDN by default
3. **Set Cache Headers**: Use `cache-control: 3600` for better performance
4. **Compress Images**: Optimize before upload (JPEG quality 85%, WebP recommended)
5. **Lazy Loading**: Load images only when needed in your app

## Cost Optimization

- **Storage**: $0.021/GB/month
- **Bandwidth**: $0.09/GB
- **Free tier**: 1GB storage, 2GB bandwidth/month

**Tips**:
- Compress images aggressively (target <500KB per image)
- Use thumbnails (200x200) for lists, full images for details
- Cache images locally in app after first download
- Delete old user scans periodically

## Support

For issues:
1. Check Supabase Dashboard logs
2. Verify environment variables
3. Test with curl:
   ```powershell
   curl -X GET "https://your-project-id.supabase.co/storage/v1/object/public/savo-ingredients/turmeric/raw_whole.jpg"
   ```
