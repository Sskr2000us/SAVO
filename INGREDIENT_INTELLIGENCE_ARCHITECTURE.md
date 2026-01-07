# SAVO Ingredient Intelligence System - Architecture & Implementation

## 🎯 Strategic Vision

Transform SAVO from a simple ingredient scanner into a **Visual-First Ingredient Intelligence Platform** that:

1. **Identifies ingredients** through computer vision (not just barcodes)
2. **Understands culinary context** (regional variations, substitutions, pairings)
3. **Prevents food waste** through spoilage prediction and smart storage
4. **Educates users** with multi-language support and cultural context
5. **Learns continuously** from user confirmations and corrections

---

## 🏗️ System Architecture

### High-Level Components

```
┌─────────────────────────────────────────────────────────────────┐
│                        SAVO Mobile App                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │ Camera Scan  │  │ Search       │  │ Recipe       │         │
│  │ - Visual     │  │ - Multi-lang │  │ - Smart Sub  │         │
│  │ - Barcode    │  │ - Voice      │  │ - Pairings   │         │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘         │
└─────────┼──────────────────┼──────────────────┼────────────────┘
          │                  │                  │
          ▼                  ▼                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FastAPI Backend Layer                        │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐   │
│  │ Visual Intel   │  │ Search Engine  │  │ Graph Engine   │   │
│  │ Endpoints      │  │ Endpoints      │  │ Endpoints      │   │
│  └────────┬───────┘  └────────┬───────┘  └────────┬───────┘   │
└───────────┼──────────────────────┼────────────────────┼─────────┘
            │                     │                    │
            ▼                     ▼                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Service Layer                              │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐   │
│  │ CV Processor   │  │ Embedding      │  │ Graph Resolver │   │
│  │ - GPT-4 Vision │  │ Service        │  │ - Substitutions│   │
│  │ - Color Extract│  │ - Vector Search│  │ - Confusion    │   │
│  │ - Texture Anal.│  │ - Semantic     │  │ - Pairing      │   │
│  └────────┬───────┘  └────────┬───────┘  └────────┬───────┘   │
└───────────┼──────────────────────┼────────────────────┼─────────┘
            │                     │                    │
            ▼                     ▼                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                       Data Layer                                │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐   │
│  │ PostgreSQL     │  │ Supabase       │  │ Vector DB      │   │
│  │ - Master Data  │  │ Storage        │  │ (pgvector)     │   │
│  │ - Relationships│  │ - Images       │  │ - Embeddings   │   │
│  │ - User Data    │  │ - Thumbnails   │  │ - Similarity   │   │
│  └────────────────┘  └────────────────┘  └────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📊 Enhanced Database Schema

### New Tables Required

```sql
-- 1. Enhanced master_ingredients (extend existing)
ALTER TABLE master_ingredients ADD COLUMN IF NOT EXISTS
    ingredient_type TEXT DEFAULT 'single_ingredient', -- single, blend, composite
    scientific_name TEXT,
    status TEXT DEFAULT 'active', -- active, deprecated, seasonal
    
    -- Visual intelligence
    visual_states TEXT[], -- raw_whole, raw_cut, powdered, cooked
    dominant_colors TEXT[],
    shape_features TEXT[],
    surface_texture TEXT[],
    
    -- Sensory
    taste_profile TEXT[],
    aroma_profile TEXT[],
    mouthfeel TEXT[],
    intensity_level TEXT,
    heat_level TEXT,
    
    -- Culinary
    common_uses TEXT[],
    cooking_methods TEXT[],
    
    -- Storage
    storage_conditions JSONB,
    shelf_life_days JSONB, -- {fresh: 30, powder: 180}
    waste_risk_level TEXT,
    spoilage_signs TEXT[],
    
    -- AI metadata
    cv_labels TEXT[],
    embedding_tags TEXT[],
    llm_prompt_hints TEXT[],
    confidence_threshold NUMERIC(3,2) DEFAULT 0.85;

-- 2. ingredient_aliases (multi-language names)
CREATE TABLE ingredient_aliases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ingredient_id UUID REFERENCES master_ingredients(id) ON DELETE CASCADE,
    alias_name TEXT NOT NULL,
    language_code TEXT NOT NULL, -- hi-IN, ta-IN, es-ES
    region TEXT,
    is_primary BOOLEAN DEFAULT false,
    usage_frequency INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_aliases_ingredient ON ingredient_aliases(ingredient_id);
CREATE INDEX idx_aliases_name ON ingredient_aliases(alias_name);
CREATE INDEX idx_aliases_language ON ingredient_aliases(language_code);

-- 3. ingredient_images (organized image sets)
CREATE TABLE ingredient_images (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ingredient_id UUID REFERENCES master_ingredients(id) ON DELETE CASCADE,
    image_id TEXT UNIQUE NOT NULL,
    
    -- Storage
    storage_uri TEXT NOT NULL, -- s3:// or supabase://
    thumbnail_uri TEXT,
    
    -- Context
    visual_state TEXT NOT NULL, -- raw_whole, powdered, cooked
    lighting_type TEXT, -- natural, indoor, studio
    background_type TEXT, -- market, kitchen, bowl, plate
    angle TEXT, -- top, side, 45deg
    
    -- Quality
    resolution_width INTEGER,
    resolution_height INTEGER,
    file_size_bytes BIGINT,
    
    -- AI metadata
    is_verified BOOLEAN DEFAULT false,
    verification_source TEXT, -- human, ai_confident, ai_uncertain
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_images_ingredient ON ingredient_images(ingredient_id);
CREATE INDEX idx_images_state ON ingredient_images(visual_state);

-- 4. ingredient_substitutions (directed graph)
CREATE TABLE ingredient_substitutions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_ingredient_id UUID REFERENCES master_ingredients(id) ON DELETE CASCADE,
    target_ingredient_id UUID REFERENCES master_ingredients(id) ON DELETE CASCADE,
    
    -- Relationship
    substitution_type TEXT NOT NULL, -- primary, emergency, regional, dietary
    similarity_score NUMERIC(3,2) NOT NULL, -- 0.0 to 1.0
    
    -- Context
    applicable_forms TEXT[], -- fresh, dried, powdered
    applicable_dishes TEXT[], -- curries, stews, marinades
    notes TEXT,
    
    -- Usage stats
    user_acceptance_rate NUMERIC(3,2),
    times_suggested INTEGER DEFAULT 0,
    times_accepted INTEGER DEFAULT 0,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_substitutions_source ON ingredient_substitutions(source_ingredient_id);
CREATE INDEX idx_substitutions_target ON ingredient_substitutions(target_ingredient_id);
CREATE INDEX idx_substitutions_score ON ingredient_substitutions(similarity_score DESC);

-- 5. ingredient_confusion (disambiguation)
CREATE TABLE ingredient_confusion (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ingredient_a_id UUID REFERENCES master_ingredients(id) ON DELETE CASCADE,
    ingredient_b_id UUID REFERENCES master_ingredients(id) ON DELETE CASCADE,
    
    -- Confusion details
    confusion_reason TEXT NOT NULL, -- similar_appearance, similar_name, same_category
    confusion_frequency INTEGER DEFAULT 0, -- how often confused
    
    -- Disambiguation
    disambiguation_rules TEXT[],
    key_visual_differences TEXT[],
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_confusion_a ON ingredient_confusion(ingredient_a_id);
CREATE INDEX idx_confusion_b ON ingredient_confusion(ingredient_b_id);

-- 6. ingredient_pairings (culinary intelligence)
CREATE TABLE ingredient_pairings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ingredient_a_id UUID REFERENCES master_ingredients(id) ON DELETE CASCADE,
    ingredient_b_id UUID REFERENCES master_ingredients(id) ON DELETE CASCADE,
    
    -- Pairing strength
    pairing_score NUMERIC(3,2) NOT NULL, -- 0.0 to 1.0
    pairing_type TEXT, -- classic, modern, regional, experimental
    
    -- Context
    cuisine_types TEXT[], -- indian, italian, chinese
    dish_types TEXT[], -- curry, pasta, stir_fry
    
    -- Evidence
    source TEXT, -- recipe_analysis, expert_knowledge, user_behavior
    times_used_together INTEGER DEFAULT 0,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_pairings_a ON ingredient_pairings(ingredient_a_id);
CREATE INDEX idx_pairings_b ON ingredient_pairings(ingredient_b_id);
CREATE INDEX idx_pairings_score ON ingredient_pairings(pairing_score DESC);

-- 7. regional_variants (geographic variations)
CREATE TABLE ingredient_regional_variants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ingredient_id UUID REFERENCES master_ingredients(id) ON DELETE CASCADE,
    
    -- Location
    region TEXT NOT NULL, -- India, Thailand, Mexico
    country_code TEXT,
    
    -- Variant details
    variant_notes TEXT,
    flavor_differences TEXT[],
    appearance_differences TEXT[],
    typical_uses TEXT[],
    
    -- Sourcing
    is_native BOOLEAN DEFAULT false,
    availability_level TEXT, -- abundant, common, rare, imported
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_variants_ingredient ON ingredient_regional_variants(ingredient_id);
CREATE INDEX idx_variants_region ON ingredient_regional_variants(region);

-- 8. ingredient_embeddings (vector search)
CREATE TABLE ingredient_embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ingredient_id UUID REFERENCES master_ingredients(id) ON DELETE CASCADE,
    
    -- Vector data (requires pgvector extension)
    text_embedding VECTOR(1536), -- OpenAI ada-002
    image_embedding VECTOR(512), -- CLIP or similar
    
    -- Metadata
    embedding_model TEXT NOT NULL,
    embedding_version TEXT,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_embeddings_ingredient ON ingredient_embeddings(ingredient_id);
-- Vector similarity indexes (after enabling pgvector)
-- CREATE INDEX idx_embeddings_text ON ingredient_embeddings USING ivfflat (text_embedding vector_cosine_ops);
-- CREATE INDEX idx_embeddings_image ON ingredient_embeddings USING ivfflat (image_embedding vector_cosine_ops);

-- 9. visual_scan_results (CV processing logs)
CREATE TABLE visual_scan_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    
    -- Input
    scan_image_url TEXT NOT NULL,
    scan_type TEXT NOT NULL, -- ingredient_identification, quality_check, quantity_estimate
    
    -- Detection results
    detected_ingredients JSONB, -- [{"ingredient_id": "...", "confidence": 0.85}]
    visual_features JSONB, -- {"colors": [...], "textures": [...]}
    
    -- User feedback
    user_confirmed_ingredient_id UUID REFERENCES master_ingredients(id),
    was_correct BOOLEAN,
    correction_reason TEXT,
    
    -- Performance
    processing_time_ms INTEGER,
    model_version TEXT,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_visual_scans_user ON visual_scan_results(user_id);
CREATE INDEX idx_visual_scans_confirmed ON visual_scan_results(user_confirmed_ingredient_id);
```

---

## 🚀 Implementation Phases

### **Phase 1: Foundation (Week 1-2)** ✅ COMPLETED
- [x] Basic master_ingredients table
- [x] Product barcodes integration
- [x] OpenFoodFacts API
- [x] **NEW**: Created 9 new intelligence tables (migration 005)
- [x] **NEW**: Extended master_ingredients with 20+ intelligence fields
- [x] **NEW**: Deployed migration 005 to production
- [x] **NEW**: Created seed script with detailed ingredient data
- [x] **NEW**: Expanded to 37 ingredients across all major categories (spices, vegetables, grains, proteins, dairy, herbs, oils)
- [x] **NEW**: Seeded 222 multi-language aliases (6 languages: English, Hindi, Tamil, Spanish, Chinese, Arabic)
- [x] **NEW**: Created Supabase Storage setup script (setup_storage_buckets.py)
- [ ] **PENDING**: Continue expansion to 100+ ingredients (63 more needed)
- [ ] **PENDING**: Execute Supabase Storage bucket creation and upload reference images

### **Phase 2: Visual Intelligence (Week 3-4)** ✅ COMPLETED
- [x] Image upload and storage system
- [x] Color extraction service (PIL/OpenCV with k-means clustering)
- [x] Texture analysis (basic CV using variance detection)
- [x] GPT-4 Vision integration for ingredient ID
- [x] Visual similarity search (color histogram, texture matching)
- [x] User confirmation feedback loop
- [x] FastAPI endpoints (identify-ingredient, extract-features, similar-ingredients, confirm-identification)
- [x] Flutter mobile integration (camera/gallery, real-time processing, result display)

### **Phase 3: Search & Discovery (Week 5-6)** ✅ COMPLETED
- [x] Multi-language search (existing + aliases)
- [x] Vector embeddings generation (OpenAI ada-002)
- [x] Semantic search with pgvector
- [x] Fuzzy matching for typos (Levenshtein distance, fuzzywuzzy)
- [x] Voice search support (speech-to-text optimized)
- [x] Hybrid search (combines multi-language, fuzzy, and semantic)
- [x] Autocomplete suggestions
- [x] FastAPI search endpoints (7 endpoints)
- [x] Flutter search service integration

### **Phase 4: Graph Intelligence (Week 7-8)** ✅ COMPLETED
- [x] Substitution recommendation engine (context-aware, similarity-scored)
- [x] Confusion disambiguation system (visual feature matching)
- [x] Ingredient pairing suggestions (classic, modern, regional)
- [x] Recipe compatibility scoring (harmony analysis)
- [x] Smart grocery list optimization (consolidation, substitutions)
- [x] User feedback learning system
- [x] FastAPI graph endpoints (7 endpoints)
- [x] Flutter graph intelligence service integration
- [x] Graph data seeding (35+ substitutions, 10+ confusions, 35+ pairings)

### **Phase 5: Regional Intelligence (Week 9-10)**
- [x] Regional variant database
- [x] Cuisine-specific recommendations
- [x] Cultural context in recipes
- [x] Seasonal availability tracking
- [x] Local sourcing suggestions
- [x] FastAPI regional endpoints (8 endpoints + utilities)
- [x] Flutter regional intelligence service integration
- [x] Regional data seeding (42+ regional variants across 14 ingredients)

### **Phase 6: Waste Prevention (Week 11-12)**
- [ ] Spoilage prediction models
- [ ] Expiry date tracking (existing + enhanced)
- [ ] Storage condition alerts
- [ ] Use-by-date recipe suggestions
- [ ] Waste analytics dashboard

---

## 🔧 New Services Required

### 1. **Visual Intelligence Service**
```python
# services/api/app/services/visual_intelligence.py

class VisualIntelligenceService:
    def __init__(self):
        self.vision_client = OpenAIVisionClient()
        self.color_extractor = ColorExtractor()
        
    async def identify_ingredient(
        self, 
        image_url: str,
        context: dict = None
    ) -> IngredientIdentificationResult:
        """
        Identify ingredient from image using multi-step process:
        1. Extract visual features (color, texture, shape)
        2. Query GPT-4 Vision with context
        3. Match against master_ingredients
        4. Check confusion graph for disambiguation
        5. Return ranked results with confidence
        """
        
    async def extract_visual_signature(self, image_url: str) -> dict:
        """Extract color, texture, shape features"""
        
    async def find_visually_similar(
        self, 
        ingredient_id: UUID, 
        limit: int = 10
    ) -> List[SimilarIngredient]:
        """Find ingredients with similar visual features"""
```

### 2. **Graph Intelligence Service**
```python
# services/api/app/services/graph_intelligence.py

class GraphIntelligenceService:
    async def get_substitutions(
        self,
        ingredient_id: UUID,
        context: SubstitutionContext
    ) -> List[SubstitutionSuggestion]:
        """
        Find best substitutes based on:
        - Similarity score
        - Context (dish type, cuisine, dietary)
        - User preferences
        - Availability
        """
        
    async def resolve_confusion(
        self,
        detected_ingredients: List[UUID],
        image_url: str
    ) -> DisambiguationResult:
        """
        When multiple similar ingredients detected:
        1. Check confusion graph
        2. Apply disambiguation rules
        3. Extract key visual differences
        4. Return best match
        """
        
    async def get_pairings(
        self,
        ingredient_ids: List[UUID],
        cuisine_type: str = None
    ) -> List[IngredientPairing]:
        """Suggest complementary ingredients"""
```

### 3. **Embedding Service**
```python
# services/api/app/services/embedding_service.py

class EmbeddingService:
    def __init__(self):
        self.openai_client = OpenAI()
        
    async def generate_text_embedding(
        self,
        text: str
    ) -> List[float]:
        """Generate text embedding for search"""
        
    async def generate_image_embedding(
        self,
        image_url: str
    ) -> List[float]:
        """Generate image embedding using CLIP"""
        
    async def semantic_search(
        self,
        query: str,
        limit: int = 20
    ) -> List[SearchResult]:
        """
        Search ingredients using vector similarity:
        1. Generate query embedding
        2. Find nearest neighbors in pgvector
        3. Rank by relevance
        4. Apply filters (category, region, etc.)
        """
```

---

## 📡 New API Endpoints

```python
# Visual Intelligence Endpoints
POST   /api/intelligence/identify-ingredient
POST   /api/intelligence/extract-visual-features
GET    /api/intelligence/similar-ingredients/{ingredient_id}

# Search Endpoints
GET    /api/intelligence/search
POST   /api/intelligence/semantic-search
POST   /api/intelligence/voice-search

# Graph Endpoints
GET    /api/intelligence/substitutions/{ingredient_id}
POST   /api/intelligence/resolve-confusion
GET    /api/intelligence/pairings

# Regional Intelligence
GET    /api/intelligence/regional-variants/{ingredient_id}
GET    /api/intelligence/regional-availability

# Training & Feedback
POST   /api/intelligence/confirm-identification
POST   /api/intelligence/report-confusion
POST   /api/intelligence/rate-substitution
```

---

## 🔄 Migration Path

### Step 1: Database Migration ✅ COMPLETED
```bash
# Created migration file
# services/api/migrations/005_ingredient_intelligence.sql
# - 9 new tables created
# - 20+ new columns added to master_ingredients
# - 3 helper functions created
# - RLS policies enabled

# Migration deployed to production: 2026-01-06
# Status: Successfully executed on Supabase
```

### Step 2: Seed Master Data ✅ PARTIALLY COMPLETED
```bash
# Seed script created and executed
python services/api/scripts/seed_ingredient_intelligence.py

# Currently seeded (9 ingredients, 54 aliases):
# ✅ Spices: Turmeric, Ginger, Cumin, Coriander
# ✅ Vegetables: Tomato, Onion, Garlic
# ✅ Grains/Legumes: Basmati Rice, Red Lentils

# Next batch (expand to 100+):
# - More spices: Black Pepper, Cardamom, Cinnamon, Cloves
# - More vegetables: Potato, Spinach, Cauliflower, Carrot
# - More grains: Wheat flour, Chickpeas, Black lentils
# - Proteins: Chicken, Paneer, Tofu, Eggs
# - Dairy: Milk, Yogurt, Ghee, Butter
```

### Step 3: Image Collection
```bash
# Set up Supabase Storage buckets
# - savo-ingredients (raw images)
# - savo-ingredients-thumbnails (optimized)
# - savo-user-scans (user uploads)

# Upload seed images
python services/api/scripts/upload_ingredient_images.py
```

### Step 4: Generate Embeddings
```bash
# Generate text + image embeddings for all ingredients
python services/api/scripts/generate_embeddings.py
```

---

## 🎯 Key Differentiators

### 1. **Visual-First Approach**
- Users scan ingredients directly, no need to know names
- Works across languages and cultures
- Handles raw, cooked, and processed forms

### 2. **Cultural Intelligence**
- Multi-language support (Hindi, Tamil, Spanish, Chinese, Arabic)
- Regional variants (Indian turmeric vs Indonesian)
- Cuisine-specific recommendations

### 3. **Learning System**
- Learns from user confirmations
- Improves confusion disambiguation
- Tracks substitution acceptance rates

### 4. **Waste Prevention**
- Smart expiry tracking
- Recipe suggestions based on expiring items
- Storage condition monitoring

---

## 📊 Success Metrics

1. **Identification Accuracy**: >90% on first scan
2. **Multi-language Coverage**: 6+ languages
3. **Substitution Acceptance**: >70% user acceptance
4. **Waste Reduction**: 20% reduction in user food waste
5. **User Engagement**: 3x increase in scanning frequency

---

## 🛠️ Implementation Status & Next Steps

### ✅ Completed (2026-01-06)
1. ✅ **Migration 005** created and deployed
   - 9 new tables with full schema
   - 20+ intelligence fields on master_ingredients
   - Helper functions for substitutions, pairings, search
   
2. ✅ **Seed script** created and executed
   - 37 ingredients with full intelligence data across all categories:
     * Spices: Turmeric, Cumin, Coriander, Ginger, Black Pepper, Cardamom, Cinnamon, Cloves, Mustard Seeds, Bay Leaves
     * Vegetables: Tomato, Onion, Garlic, Potato, Spinach, Cauliflower, Carrot, Bell Pepper, Eggplant
     * Grains/Legumes: Basmati Rice, Red Lentils, Chickpeas, Black Lentils, Wheat Flour
     * Proteins: Chicken Breast, Paneer, Tofu, Eggs
     * Dairy: Milk, Yogurt, Ghee, Butter
     * Herbs: Cilantro, Mint, Curry Leaves
     * Oils: Mustard Oil, Coconut Oil
   - 222 multi-language aliases (English, Hindi, Tamil, Spanish, Chinese, Arabic)
   - Visual features, sensory profiles, storage data
   - AI training metadata (CV labels, embeddings, LLM hints)

3. ✅ **Supabase Storage** setup script created
   - setup_storage_buckets.py for bucket creation
   - 3 buckets configured: savo-ingredients, savo-ingredients-thumbnails, savo-user-scans
   - RLS policies defined for public/private access

4. ✅ **VisualIntelligenceService** implemented
   - GPT-4 Vision integration for ingredient identification
   - Visual feature extraction (color, texture, brightness, contrast)
   - Dominant color detection using k-means clustering
   - Similarity calculation for visual matching
   - Context-aware identification prompts

5. ✅ **FastAPI Endpoints** created
   - POST /api/intelligence/identify-ingredient (GPT-4 Vision powered)
   - POST /api/intelligence/extract-visual-features
   - GET /api/intelligence/similar-ingredients/{id}
   - POST /api/intelligence/confirm-identification (feedback loop)
   - Image upload support (JPEG, PNG, WebP)
   - Database integration for ingredient matching

6. ✅ **Flutter Mobile Integration** implemented
   - visual_intelligence_service.dart (Dart service layer)
   - camera_scan_screen.dart (UI with camera/gallery support)
   - Real-time ingredient identification
   - Result display with confidence scores
   - Visual features visualization
   - Add to inventory integration

7. ✅ **Search & Discovery System** implemented
   - embedding_service.py (OpenAI ada-002 integration)
   - generate_embeddings.py (batch embedding generation script)
   - search_service.py (multi-language, fuzzy, semantic, voice, hybrid search)
   - search.py (FastAPI router with 7 endpoints)
   - search_service.dart (Flutter integration)
   - Supports: exact match, partial match, fuzzy (typo tolerance), semantic (concept matching), voice search
   - Autocomplete suggestions for search input
   - Multi-method result boosting

8. ✅ **Graph Intelligence System** implemented
   - graph_intelligence_service.py (substitutions, confusions, pairings, recipe compatibility, grocery optimization)
   - seed_graph_data.py (35+ substitutions, 10+ confusions, 35+ pairings)
   - graph.py (FastAPI router with 7 endpoints)
   - graph_intelligence_service.dart (Flutter integration)
   - Features: context-aware substitutions, visual disambiguation, pairing suggestions, compatibility scoring
   - User feedback learning for continuous improvement

9. ✅ **Regional Intelligence System** implemented
   - regional_intelligence_service.py (regional variants, cuisine recommendations, cultural context, seasonal availability, local sourcing)
   - seed_regional_data.py (42+ regional variants for 14 ingredients across 14+ regions)
   - regional.py (FastAPI router with 8 endpoints + utilities)
   - regional_intelligence_service.dart (Flutter integration)
   - Features: multi-region support, seasonal tracking, native/imported classification, cuisine comparison
   - Supports: India, China, Thailand, Japan, Italy, Greece, Turkey, Mexico, Peru, Caribbean, Middle East, Southeast Asia, Mediterranean, United States

### 🔄 In Progress
10. **Expand ingredient database** to 100+ ingredients
   - Need: 60+ more ingredients across all categories
   - Regional variants (Indian, Chinese, Mexican cuisines)
   - Seasonal ingredients
   - More herbs, spices, and specialty items

### 📋 Upcoming (Phase 6+)
11. **Upload reference images** to Supabase Storage
   - Create image dataset for each ingredient
   - Multiple states (raw, cut, powdered, cooked)
   - Various backgrounds and lighting conditions
   - Generate thumbnails for fast loading

12. **Seed graph data** for intelligent recommendations
    - Run: `python services/api/scripts/seed_graph_data.py`
    - Creates substitutions, confusions, and pairings
    - Enables graph intelligence features

13. **Generate embeddings** for semantic search
    - Run: `python services/api/scripts/generate_embeddings.py`
    - Requires: OPENAI_API_KEY environment variable
    - Creates embeddings for all 37 ingredients
    - Enables semantic search functionality

14. **Implement Phase 6: Waste Prevention**
    - Spoilage prediction models
    - Expiry date tracking and alerts
    - Storage condition monitoring
    - Use-by-date recipe suggestions
    - Waste analytics dashboard

15. **Test and optimize**
    - End-to-end testing with real images
    - Performance optimization (caching, compression)
    - Confidence threshold tuning
    - User acceptance testing
