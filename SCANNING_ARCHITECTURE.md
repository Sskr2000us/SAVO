# Advanced Scanning Architecture Flow

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    SAVO SCANNING SYSTEM                         │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │
│  │   Barcode    │  │  Container   │  │   Vision     │        │
│  │   Scanning   │  │  Recognition │  │   Scanning   │        │
│  └──────────────┘  └──────────────┘  └──────────────┘        │
│         │                 │                  │                 │
│         └─────────────────┴──────────────────┘                 │
│                           │                                     │
│                    ┌──────▼──────┐                            │
│                    │ Orchestrator │                            │
│                    └──────┬──────┘                            │
│                           │                                     │
│         ┌─────────────────┼─────────────────┐                 │
│         │                 │                 │                 │
│   ┌─────▼─────┐    ┌─────▼─────┐    ┌─────▼─────┐          │
│   │  OpenAI   │    │ OpenFood  │    │ Quantity  │          │
│   │  Vision   │    │  Facts    │    │ Estimator │          │
│   │ (GPT-4o)  │    │    API    │    │           │          │
│   └───────────┘    └───────────┘    └───────────┘          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    DATABASE LAYER                               │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │
│  │   master_    │  │   product_   │  │  container_  │        │
│  │ ingredients  │  │   barcodes   │  │    scans     │        │
│  └──────────────┘  └──────────────┘  └──────────────┘        │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │
│  │ ingredient_  │  │   quantity_  │  │   barcode_   │        │
│  │  densities   │  │ calibrations │  │    scans     │        │
│  └──────────────┘  └──────────────┘  └──────────────┘        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Feature Breakdown

### 1️⃣ **Barcode Scanning Flow**

```
User Scans Package
        ↓
┌───────────────────┐
│  Barcode Reader   │
│  (EAN-13/UPC-A)   │
└─────────┬─────────┘
          ↓
    Check Cache?
    ┌─────┴─────┐
   YES          NO
    ↓            ↓
┌─────────┐  ┌──────────────┐
│  Local  │  │ OpenFoodFacts│
│   DB    │  │  API Lookup  │
└────┬────┘  └──────┬───────┘
     │              │
     │     ┌────────┘
     │     │ Cache Result
     ↓     ↓
┌─────────────────┐
│ Extract Product │
│ - Name          │
│ - Brand         │
│ - Quantity      │
│ - Nutrition     │
└────────┬────────┘
         ↓
┌─────────────────┐
│ Match to Master │
│   Ingredients   │
└────────┬────────┘
         ↓
┌─────────────────┐
│ Add to Inventory│
└─────────────────┘
```

### 2️⃣ **Container Recognition Flow**

```
User Uploads Image
        ↓
┌───────────────────┐
│ Image Preprocessing│
└─────────┬─────────┘
          ↓
┌───────────────────────────────────────┐
│      Enhanced GPT-4o Vision           │
│                                       │
│  Analyze:                             │
│  1. Container type (jar/bottle/etc)   │
│  2. Material (glass/plastic)          │
│  3. Transparency level                │
│  4. Visual Cues:                      │
│     - Color (white/brown/yellow)      │
│     - Texture (grainy/powdery)        │
│     - Particle size                   │
│  5. Reference objects (hand/coin)     │
│  6. Fill percentage (0-100%)          │
│                                       │
└─────────┬─────────────────────────────┘
          ↓
┌───────────────────┐
│ Identify Ingredient│
│ from Visual Cues  │
└─────────┬─────────┘
          ↓
┌───────────────────┐
│ Quantity Estimator│
│                   │
│ 1. Scale Factor   │
│    (from ref obj) │
│ 2. Volume Calc    │
│ 3. Density Lookup │
│ 4. Weight = Vol × │
│            Density│
└─────────┬─────────┘
          ↓
┌───────────────────┐
│ Return Results:   │
│ - Ingredient      │
│ - Quantity (g/ml) │
│ - Confidence      │
└───────────────────┘
```

### 3️⃣ **Quantity Estimation Model**

```
Input: Ingredient Bounding Box + Reference Objects
        ↓
┌───────────────────────────────────────┐
│     Reference Object Detection        │
│                                       │
│  Detected: Hand (18cm)                │
│  Bounding Box: [50, 100, 150, 300]   │
│  Scale: 5.5 pixels/cm                 │
└─────────┬─────────────────────────────┘
          ↓
┌───────────────────────────────────────┐
│     Calculate Real Dimensions         │
│                                       │
│  Ingredient Width:  10cm              │
│  Ingredient Height: 15cm              │
│  Estimated Depth:   8cm (heuristic)   │
└─────────┬─────────────────────────────┘
          ↓
┌───────────────────────────────────────┐
│     Volume Calculation                │
│                                       │
│  Volume = Width × Height × Depth      │
│  Volume = 10 × 15 × 8 = 1200 cm³      │
│  Volume = 1200 ml                     │
└─────────┬─────────────────────────────┘
          ↓
┌───────────────────────────────────────┐
│     Density Lookup                    │
│                                       │
│  Ingredient: Rice                     │
│  Density: 0.75 g/ml                   │
└─────────┬─────────────────────────────┘
          ↓
┌───────────────────────────────────────┐
│     Weight Conversion                 │
│                                       │
│  Weight = Volume × Density            │
│  Weight = 1200 ml × 0.75 g/ml         │
│  Weight = 900g                        │
│  Confidence: 0.72                     │
└───────────────────────────────────────┘
```

### 4️⃣ **Multi-Language Search**

```
User Query: "चावल" (Hindi for Rice)
        ↓
┌───────────────────────────────────────┐
│  search_ingredients_multilang()       │
│                                       │
│  Search Fields:                       │
│  - canonical_name                     │
│  - names->>'hi'  (Hindi)              │
│  - names->>'en'  (English)            │
│  - names->>'ta'  (Tamil)              │
│  - All other languages                │
└─────────┬─────────────────────────────┘
          ↓
┌───────────────────────────────────────┐
│        Relevance Scoring              │
│                                       │
│  Exact canonical match:     1.0       │
│  Match in search language:  0.9       │
│  Match in English:          0.8       │
│  Match in other language:   0.5       │
└─────────┬─────────────────────────────┘
          ↓
┌───────────────────────────────────────┐
│           Results                     │
│                                       │
│  1. Rice (चावल)         - 0.95        │
│  2. Basmati Rice (बासमती) - 0.90     │
│  3. Brown Rice (ब्राउन)   - 0.85     │
└───────────────────────────────────────┘
```

---

## Database Relationships

```
┌─────────────────────┐
│  master_ingredients │ ← Global ingredient reference
│  ─────────────────  │
│  • canonical_name   │
│  • names (JSONB)    │
│  • density_g_per_ml │
│  • category         │
└──────────┬──────────┘
           │
           │ 1:N
           ↓
┌─────────────────────┐
│  ingredient_        │
│  densities          │
│  ─────────────────  │
│  • form (raw/cooked)│
│  • density_g_per_ml │
└─────────────────────┘

┌─────────────────────┐
│  product_barcodes   │ ← Barcode database
│  ─────────────────  │
│  • upc_ean          │
│  • product_name     │
│  • brand            │
│  • quantity_value   │
└──────────┬──────────┘
           │
           │ N:1
           ↓
┌─────────────────────┐
│  master_ingredients │
└─────────────────────┘

┌─────────────────────┐
│  barcode_scans      │ ← User scan history
│  ─────────────────  │
│  • user_id          │
│  • barcode          │
│  • detected info    │
└──────────┬──────────┘
           │
           │ N:1
           ↓
┌─────────────────────┐
│  inventory_items    │ ← Added to inventory
└─────────────────────┘

┌─────────────────────┐
│  container_scans    │ ← Container recognition
│  ─────────────────  │
│  • container_type   │
│  • visual_cues      │
│  • detected_ing     │
└──────────┬──────────┘
           │
           │ N:1
           ↓
┌─────────────────────┐
│  master_ingredients │
└─────────────────────┘

┌─────────────────────┐
│  quantity_          │ ← ML training data
│  calibrations       │
│  ─────────────────  │
│  • estimated_qty    │
│  • actual_qty       │
│  • error_%          │
└─────────────────────┘
```

---

## Technology Stack

| Component | Technology |
|-----------|-----------|
| **Backend** | FastAPI (Python 3.13) |
| **Vision AI** | OpenAI GPT-4o Vision |
| **Barcode Lookup** | OpenFoodFacts API (Free) |
| **Database** | PostgreSQL (Supabase) |
| **Image Storage** | Supabase Storage |
| **Quantity Estimation** | Custom ML Model (Python) |
| **Multi-Language** | JSONB + PostgreSQL GIN Index |
| **Deployment** | Render.com (Auto-deploy) |

---

## Performance Metrics

### **Barcode Scanning**
- **Lookup Speed:** <100ms (cached), <2s (API)
- **Success Rate:** 95% (OpenFoodFacts coverage)
- **Confidence:** 0.95 (verified products)

### **Container Recognition**
- **Processing Time:** 3-5s (GPT-4o Vision)
- **Ingredient Accuracy:** 80-90% (with clear visual cues)
- **Quantity Confidence:** 60-80% (with reference objects)

### **Quantity Estimation**
- **With Reference Object:** ±15-20% error
- **Without Reference Object:** ±30-50% error
- **Best Case:** ±10% (calibrated containers)

---

## Future Enhancements

### **Phase 2** (Q1 2026)
- [ ] Expiry date OCR extraction
- [ ] Video scanning for multiple items
- [ ] Crowdsourced ingredient images
- [ ] Real-time confidence feedback

### **Phase 3** (Q2 2026)
- [ ] Fine-tuned ML model for quantity
- [ ] Regional ingredient databases (200+ items per region)
- [ ] DALL-E integration for missing images
- [ ] Offline barcode database sync

### **Phase 4** (Q3 2026)
- [ ] AR overlay for quantity estimation
- [ ] Smart shopping list from scans
- [ ] Nutritional analysis from barcodes
- [ ] Recipe suggestions from scanned items

---

**Architecture Version:** 1.0  
**Last Updated:** January 6, 2026  
**Status:** ✅ Production Ready
