# Advanced Scanning Features - Implementation Guide

## Overview
This implementation adds **global ingredient database**, **barcode scanning**, **container recognition**, and **quantity estimation** to the SAVO scanning system.

---

## ✅ Implemented Features

### 1. **Global Ingredients Database**
- **Master ingredients table** with multi-language support
- Languages: English, Hindi, Tamil, Spanish, Chinese, Arabic
- Regional variants (e.g., paneer/cottage cheese)
- Default images and density data
- 25+ seeded ingredients (expandable to 200+)

### 2. **Barcode Scanning**
- **OpenFoodFacts API integration** (free, crowd-sourced global database)
- EAN-13 / UPC-A barcode recognition
- Automatic product information extraction
- Quantity and unit parsing
- Automatic inventory addition
- Barcode caching for offline lookup

### 3. **Container Recognition**
- **GPT-4o Vision** enhanced for containers
- Transparent/glass jar detection
- Ingredient identification through visual cues:
  - Color (white, brown, yellow, etc.)
  - Texture (grainy, powdery, liquid)
  - Particle size (fine, small grains, chunky)
- Container types: mason jar, plastic container, glass bottle, ziplock bag

### 4. **Quantity Estimation**
- **Reference object detection** (hand, coin, credit card, spoon)
- Volume calculation from bounding boxes
- Density-based weight conversion
- Container fill percentage estimation
- Confidence scoring for accuracy
- ML-ready calibration data collection

### 5. **Multi-Language Ingredient Search**
- Search in any language (Hindi: दाल, Tamil: அரிசி, etc.)
- Cross-language matching
- Relevance scoring

---

## 🗄️ Database Schema

### New Tables Created

```sql
-- 1. master_ingredients: Global ingredient reference
-- 2. product_barcodes: UPC/EAN barcode database
-- 3. ingredient_densities: Density lookup for quantity estimation
-- 4. quantity_calibrations: ML training data
-- 5. container_scans: Container recognition results
-- 6. barcode_scans: Barcode scan history
-- 7. reference_objects: Size estimation reference data
-- 8. receipt_items: Enhanced receipt item storage
```

**Migration File:** `services/api/migrations/004_global_ingredients_and_barcode.sql`

---

## 📡 API Endpoints

### **1. Barcode Scanning**
```http
POST /api/scanning/barcode
Content-Type: application/json

{
  "barcode": "8901234567890",
  "add_to_inventory": true,
  "quantity": 500,
  "storage_location": "pantry"
}
```

**Response:**
```json
{
  "scan_id": "uuid",
  "barcode": "8901234567890",
  "product_name": "Tata Salt",
  "brand": "Tata",
  "quantity_value": 1000,
  "quantity_unit": "g",
  "ingredient_canonical_name": "salt",
  "confidence": 0.95,
  "data_source": "openfoodfacts",
  "added_to_inventory": true
}
```

### **2. Container Scanning**
```http
POST /api/scanning/container
Content-Type: multipart/form-data

image: <file>
scan_type: container
expected_ingredient: rice
```

**Response:**
```json
{
  "scan_id": "uuid",
  "container_type": "glass_jar",
  "container_material": "glass",
  "transparency_level": "transparent",
  "detected_ingredient": "rice",
  "visual_cues": {
    "color": "white",
    "texture": "grainy",
    "particle_size": "small_grains"
  },
  "estimated_quantity": 750.5,
  "estimated_unit": "g",
  "confidence_ingredient": 0.85,
  "confidence_quantity": 0.72
}
```

### **3. Multi-Language Ingredient Search**
```http
GET /api/scanning/ingredients/search-global?query=दाल&lang=hi&limit=20
```

**Response:**
```json
[
  {
    "id": "uuid",
    "canonical_name": "lentils_red",
    "matched_name": "मसूर दाल",
    "match_language": "hi",
    "category": "pulses",
    "default_image_url": "https://...",
    "relevance": 0.95
  }
]
```

---

## 🚀 Deployment Steps

### **Step 1: Run Database Migration**
```powershell
# Connect to Supabase
$env:DATABASE_URL = "postgresql://user:pass@db.xxx.supabase.co:5432/postgres"

# Run migration
psql $env:DATABASE_URL -f services\api\migrations\004_global_ingredients_and_barcode.sql
```

### **Step 2: Seed Master Ingredients**
```powershell
cd services\api

# Set database URL
$env:DATABASE_URL = "postgresql://..."

# Run seed script
python scripts\seed_master_ingredients.py
```

**Expected Output:**
```
✓ Inserted rice
✓ Inserted basmati_rice
✓ Inserted wheat_flour
...
=== Seed Complete ===
Inserted: 25
Skipped: 0
Total: 25
```

### **Step 3: Add Dependencies**
```powershell
# Add to requirements.txt
echo "httpx==0.25.2" >> requirements.txt

# Deploy to Render
git add -A
git commit -m "Add advanced scanning features with barcode and container recognition"
git push
```

### **Step 4: Configure Environment Variables**
No additional environment variables needed - uses existing OpenAI API key.

---

## 🧪 Testing

### **Test Barcode Scanning**
```powershell
# Example: Scan Tata Salt barcode
curl -X POST https://your-api.onrender.com/api/scanning/barcode `
  -H "Authorization: Bearer $TOKEN" `
  -H "Content-Type: application/json" `
  -d '{
    "barcode": "8901234567890",
    "add_to_inventory": true
  }'
```

### **Test Container Scanning**
```powershell
# Upload image of rice in jar
curl -X POST https://your-api.onrender.com/api/scanning/container `
  -H "Authorization: Bearer $TOKEN" `
  -F "image=@rice_jar.jpg" `
  -F "scan_type=container"
```

### **Test Multi-Language Search**
```powershell
# Search in Hindi
curl "https://your-api.onrender.com/api/scanning/ingredients/search-global?query=चावल&lang=hi"
```

---

## 📊 Data Flow

### **Barcode Scanning Flow**
```
1. User scans barcode → POST /api/scanning/barcode
2. Check local cache (product_barcodes table)
3. If not found → Query OpenFoodFacts API
4. Parse product data (name, brand, quantity)
5. Match to master_ingredients
6. Add to inventory_items (if requested)
7. Save to barcode_scans history
```

### **Container Scanning Flow**
```
1. User uploads container image → POST /api/scanning/container
2. Enhanced GPT-4o Vision prompt:
   - Identify container type
   - Detect visual cues (color, texture, particle size)
   - Locate reference objects (hand, coin, etc.)
3. QuantityEstimator calculates:
   - Scale factor from reference objects
   - Volume from bounding box + depth estimation
   - Weight using density lookup
4. Save to container_scans table
5. Return detected ingredient + quantity
```

---

## 🔧 Configuration

### **Quantity Estimation Tuning**

Edit `app/core/quantity_estimator.py` to adjust:

```python
# Reference object sizes (customize by region)
REFERENCE_SIZES = {
    "hand": {"length_cm": 18.0, "confidence": 0.75},
    "rupee_coin": {"diameter_cm": 2.5, "confidence": 0.95},
    ...
}

# Standard container volumes
STANDARD_CONTAINERS = {
    "mason_jar": [250, 500, 1000],
    "glass_jar": [200, 500, 750, 1000],
    ...
}
```

### **Add More Ingredients**

Edit `scripts/seed_master_ingredients.py`:

```python
MASTER_INGREDIENTS.append({
    "canonical_name": "curry_leaves",
    "names": {
        "en": "Curry Leaves",
        "hi": "कड़ी पत्ता",
        "ta": "கறிவேப்பிலை"
    },
    "category": "herbs",
    "density_g_per_ml": 0.3,
    ...
})
```

---

## 🎯 Next Steps

### **Phase 2 Enhancements**
1. **Expiry Date OCR** - Extract expiry dates from packages
2. **Barcode Scanner UI** - Mobile camera integration
3. **Crowdsourced Images** - User-contributed ingredient photos
4. **ML Model Training** - Fine-tune quantity estimation
5. **DALL-E Integration** - Generate missing ingredient images
6. **Regional Expansion** - Add 200+ more ingredients

### **Flutter Integration**
```dart
// Barcode scanning in Flutter
Future<void> scanBarcode() async {
  final barcode = await BarcodeScanner.scan();
  
  final response = await dio.post('/api/scanning/barcode', data: {
    'barcode': barcode.rawContent,
    'add_to_inventory': true,
  });
  
  // Show success dialog with product details
}
```

---

## 📝 Database Functions Reference

### **search_ingredients_multilang**
```sql
SELECT * FROM search_ingredients_multilang('rice', 'en', 20);
SELECT * FROM search_ingredients_multilang('चावल', 'hi', 20);
```

### **get_ingredient_by_barcode**
```sql
SELECT * FROM get_ingredient_by_barcode('8901234567890');
```

### **estimate_quantity_from_volume**
```sql
SELECT * FROM estimate_quantity_from_volume('rice', 500, 'raw');
-- Returns: (375.0, 'g', 0.80)
```

---

## 🐛 Troubleshooting

### **OpenFoodFacts API Timeout**
- Service has rate limits
- Cached barcodes in `product_barcodes` table
- Fallback to manual entry if not found

### **Low Quantity Estimation Confidence**
- Requires reference objects in image
- Confidence drops without scale references
- Improve by adding hand/coin to photo

### **Ingredient Not Found**
- Limited to seeded ingredients
- Add more via `seed_master_ingredients.py`
- Users can suggest new ingredients

---

## 📚 Resources

- **OpenFoodFacts API**: https://world.openfoodfacts.org/data
- **EAN Barcode Format**: https://en.wikipedia.org/wiki/International_Article_Number
- **GPT-4o Vision**: https://platform.openai.com/docs/guides/vision

---

## ✅ Checklist

- [ ] Run migration 004
- [ ] Seed master ingredients (25 items)
- [ ] Test barcode endpoint with Indian product
- [ ] Test container scanning with rice jar
- [ ] Test multi-language search in Hindi
- [ ] Add httpx to requirements.txt
- [ ] Deploy to Render
- [ ] Update Flutter app for barcode scanning

---

**Implementation Date:** January 6, 2026  
**Status:** ✅ Complete and Ready for Deployment
