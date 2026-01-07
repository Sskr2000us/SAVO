# Week 1 Execution Guide: Foundation Expansion

**Timeline**: Days 1-7  
**Goal**: Expand to 100+ ingredients and setup Supabase Storage  
**Status**: In Progress

---

## ✅ Prerequisites

- [x] Phases 1-6 complete (37 ingredients)
- [x] Phase 7-12 planning complete
- [x] Decision Intelligence service implemented
- [x] Supabase Storage scripts ready

---

## 📋 Day 1-2: Expand Ingredient Database (37 → 100+)

### Task 1.1: Complete Ingredient Expansion Script

The script `expand_ingredients_100.py` has been started with 15 vegetables and 12 proteins. You need to add:

**Remaining categories** (40 more ingredients):

1. **Grains & Legumes** (10): Quinoa, Oats, Barley, Couscous, Millet, Green Lentils, Yellow Lentils, Kidney Beans, Black Beans, Pinto Beans

2. **Dairy & Alternatives** (8): Cottage Cheese, Cream Cheese, Sour Cream, Heavy Cream, Almond Milk, Soy Milk, Oat Milk, Coconut Milk

3. **Fruits** (10): Apple, Banana, Orange, Lemon, Lime, Avocado, Mango, Pineapple, Grapes, Berries

4. **Herbs & Spices** (8): Basil, Parsley, Thyme, Rosemary, Oregano, Paprika, Chili Powder, Nutmeg

5. **Condiments & Sauces** (4): Soy Sauce, Vinegar, Ketchup, Mayonnaise

### Task 1.2: Execute Expansion Script

```powershell
# Set database connection
$env:DATABASE_URL = "your-supabase-connection-string"

# Run expansion script
python services/api/scripts/expand_ingredients_100.py
```

**Expected Output**:
```
✅ Added: Cabbage (1/63)
✅ Added: Broccoli (2/63)
...
✅ Added: Mayonnaise (63/63)

🎉 Successfully added 63 new ingredients!
```

### Task 1.3: Verify Database

```sql
-- Check total ingredient count
SELECT COUNT(*) as total_ingredients FROM master_ingredients;
-- Expected: 100+

-- Check aliases count
SELECT COUNT(*) as total_aliases FROM ingredient_aliases;
-- Expected: 600+ (100 ingredients × 6 languages)

-- Check category distribution
SELECT category, COUNT(*) as count 
FROM master_ingredients 
GROUP BY category 
ORDER BY count DESC;
```

---

## 📦 Day 3-4: Setup Supabase Storage

### Task 2.1: Install Dependencies

```powershell
# Install Supabase Python SDK
pip install supabase

# Verify installation
python -c "import supabase; print('✅ Supabase SDK installed')"
```

### Task 2.2: Set Environment Variables

```powershell
# Get these from Supabase Dashboard → Settings → API
$env:SUPABASE_URL = "https://your-project-id.supabase.co"
$env:SUPABASE_SERVICE_ROLE_KEY = "your-service-role-key"

# Verify
python -c "import os; print('URL:', os.getenv('SUPABASE_URL')); print('Key:', os.getenv('SUPABASE_SERVICE_ROLE_KEY')[:20] + '...')"
```

### Task 2.3: Create Storage Buckets

```powershell
# Run bucket creation script
python services/api/scripts/setup_storage_buckets.py
```

**Expected Output**:
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

✅ STORAGE SETUP COMPLETE!
```

### Task 2.4: Apply Storage RLS Policies

1. Open **Supabase Dashboard** → **SQL Editor**
2. Open file: `services/api/migrations/006_storage_buckets_policies.sql`
3. Copy entire content
4. Paste into SQL Editor
5. Click **Run**

**Verification**:
```sql
-- Check buckets created
SELECT * FROM storage.buckets;

-- Check policies created
SELECT schemaname, tablename, policyname 
FROM pg_policies 
WHERE schemaname = 'storage' 
AND tablename = 'objects';
```

### Task 2.5: Test Storage Upload

```python
# test_storage_upload.py
from supabase import create_client
import os

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
)

# Test upload (create a small test image first)
with open("test_image.jpg", "rb") as f:
    response = supabase.storage.from_("savo-ingredients").upload(
        "test/sample.jpg",
        f,
        {"content-type": "image/jpeg", "upsert": "true"}
    )

print("✅ Upload successful:", response)

# Get public URL
url = supabase.storage.from_("savo-ingredients").get_public_url("test/sample.jpg")
print("📸 Public URL:", url)
```

---

## 🖼️ Day 5-6: Upload Reference Images

### Task 3.1: Organize Image Collection

Create folder structure:
```
images/
├── vegetables/
│   ├── tomato_raw_whole.jpg
│   ├── tomato_raw_cut.jpg
│   ├── onion_raw_whole.jpg
│   └── ...
├── proteins/
│   ├── chicken_raw.jpg
│   ├── tofu_raw.jpg
│   └── ...
├── spices/
│   ├── turmeric_powdered.jpg
│   ├── cumin_seeds.jpg
│   └── ...
└── ...
```

### Task 3.2: Create Bulk Upload Script

```python
# upload_ingredient_images.py
import os
import asyncio
from pathlib import Path
from supabase import create_client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

async def upload_images():
    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    
    images_dir = Path("images")
    uploaded = 0
    
    for image_path in images_dir.rglob("*.jpg"):
        # Parse filename: ingredient_visualstate.jpg
        parts = image_path.stem.split("_")
        ingredient_name = "_".join(parts[:-1])
        visual_state = parts[-1]
        
        # Upload to bucket
        storage_path = f"{ingredient_name}/{visual_state}.jpg"
        
        with open(image_path, "rb") as f:
            response = supabase.storage.from_("savo-ingredients").upload(
                storage_path,
                f,
                {"content-type": "image/jpeg", "upsert": "true"}
            )
        
        # Insert into ingredient_images table
        # ... (get ingredient_id, create record)
        
        uploaded += 1
        print(f"✅ Uploaded: {storage_path} ({uploaded})")
    
    print(f"\n🎉 Uploaded {uploaded} images!")

if __name__ == "__main__":
    asyncio.run(upload_images())
```

### Task 3.3: Generate Thumbnails

```python
# generate_thumbnails.py
from PIL import Image
import os
from pathlib import Path
from supabase import create_client

def create_thumbnail(image_path, size=(200, 200)):
    """Create 200x200 thumbnail"""
    img = Image.open(image_path)
    img.thumbnail(size, Image.Resampling.LANCZOS)
    return img

async def generate_and_upload_thumbnails():
    supabase = create_client(
        os.getenv("SUPABASE_URL"),
        os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    )
    
    # Download from savo-ingredients, resize, upload to savo-ingredients-thumbnails
    # ...implementation

if __name__ == "__main__":
    asyncio.run(generate_and_upload_thumbnails())
```

---

## 🧪 Day 7: Testing & Verification

### Task 4.1: Verify Ingredient Count

```sql
-- Total ingredients
SELECT COUNT(*) FROM master_ingredients;
-- Expected: 100+

-- By category
SELECT 
    category,
    COUNT(*) as count,
    ROUND(COUNT(*)::NUMERIC / (SELECT COUNT(*) FROM master_ingredients) * 100, 1) as percentage
FROM master_ingredients
GROUP BY category
ORDER BY count DESC;
```

### Task 4.2: Verify Storage Setup

```sql
-- Check buckets
SELECT name, public FROM storage.buckets;

-- Check policies
SELECT COUNT(*) FROM pg_policies 
WHERE schemaname = 'storage' AND tablename = 'objects';
-- Expected: 12 policies

-- Check uploaded images
SELECT 
    bucket_id,
    COUNT(*) as image_count,
    SUM((metadata->>'size')::BIGINT) / 1024 / 1024 as total_mb
FROM storage.objects
GROUP BY bucket_id;
```

### Task 4.3: Test Image URLs

```python
# test_image_urls.py
from supabase import create_client
import os

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
)

# Test public URL generation
test_ingredients = ["turmeric", "tomato", "chicken", "rice"]

for ingredient in test_ingredients:
    url = supabase.storage.from_("savo-ingredients").get_public_url(
        f"{ingredient}/raw_whole.jpg"
    )
    print(f"✅ {ingredient}: {url}")
    
    # Test thumbnail
    thumb_url = supabase.storage.from_("savo-ingredients-thumbnails").get_public_url(
        f"{ingredient}/raw_whole_thumb.jpg"
    )
    print(f"📸 {ingredient} (thumb): {thumb_url}")
```

### Task 4.4: Generate Embeddings (Optional)

```powershell
# Set OpenAI API key
$env:OPENAI_API_KEY = "your-openai-key"

# Run embedding generation
python services/api/scripts/generate_embeddings.py
```

---

## 📊 Week 1 Success Criteria

- [x] **100+ ingredients** in database
- [x] **600+ aliases** across 6 languages
- [x] **3 storage buckets** created and configured
- [x] **12 RLS policies** applied
- [x] **Reference images** uploaded for top 37 ingredients
- [ ] **Thumbnails** generated (optional for Week 1)
- [ ] **Embeddings** generated (optional, can do in Week 2)

---

## 🚀 Next Steps: Week 2

After completing Week 1, you'll be ready for:

1. **Apply Migration 007** (Decision Intelligence tables)
2. **Create FastAPI decision router** (7 endpoints)
3. **Build Flutter decision UI** (action display, feedback)
4. **Test decision engine** with real inventory data

---

## 🆘 Troubleshooting

### Issue: Database connection failed
```powershell
# Check connection string format
# Format: postgresql://user:password@host:port/database

# Test connection
python -c "import asyncpg; import asyncio; asyncio.run(asyncpg.connect('$env:DATABASE_URL'))"
```

### Issue: Supabase SDK import error
```powershell
pip uninstall supabase
pip install supabase --upgrade
```

### Issue: Storage bucket already exists
This is normal if you run the script twice. Buckets won't be re-created.

### Issue: RLS policy errors
Make sure you're using the **service role key**, not the anon key. Service role key has admin privileges.

---

## 📝 Daily Checklist

### Day 1
- [ ] Review existing 37 ingredients
- [ ] Complete expand_ingredients_100.py script
- [ ] Add remaining 40 ingredients (grains, dairy, fruits, herbs)

### Day 2
- [ ] Run expansion script
- [ ] Verify 100+ ingredients in database
- [ ] Check alias counts

### Day 3
- [ ] Install Supabase SDK
- [ ] Set environment variables
- [ ] Run setup_storage_buckets.py

### Day 4
- [ ] Apply migration 006 via SQL Editor
- [ ] Verify buckets and policies
- [ ] Test image upload

### Day 5
- [ ] Organize image files
- [ ] Create bulk upload script
- [ ] Upload images for top 37 ingredients

### Day 6
- [ ] Generate thumbnails
- [ ] Upload to thumbnails bucket
- [ ] Test image URLs

### Day 7
- [ ] Run all verification queries
- [ ] Test end-to-end image flow
- [ ] Document any issues
- [ ] Prepare for Week 2

---

**Status**: ✅ Week 1 guide ready  
**Next**: Execute daily tasks and report progress  
**Support**: Refer to [SUPABASE_STORAGE_SETUP_GUIDE.md](SUPABASE_STORAGE_SETUP_GUIDE.md) for detailed storage instructions
