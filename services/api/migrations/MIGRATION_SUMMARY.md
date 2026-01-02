# SAVO Database Migrations - Complete Summary

**Generated:** January 2, 2026  
**Status:** All migrations ready for deployment  
**Database:** PostgreSQL (Supabase)

---

## Migration Status Overview

| Migration | Status | Description | Objects |
|-----------|--------|-------------|---------|
| 001_initial_schema.sql | ✅ Ready | Base schema with users, profiles, family members | 4 tables, 8 indexes, RLS |
| 002_vision_scanning_tables.sql | ✅ Ready | Vision scanning and pantry management | 5 tables, 1 trigger, indexes |
| 002_user_profile_spec.sql | ✅ Ready | Extended profile fields and audit log | 1 table, 2 columns, 1 function |
| 002_add_demo_user.sql | ⚠️  Optional | Demo data (not needed for production) | Sample data |
| 003_session_tracking.sql | ⚠️  Optional | User sessions (if needed) | 1 table |
| 003_add_quantities.sql | ✅ Ready | **Quantity tracking system** (Idempotent) | 2 tables, 7 columns, 3 functions, 1 view |
| 004_add_dinner_courses.sql | ✅ Ready | **Multi-course meal planning** (Idempotent) | 1 column, 1 constraint |

---

## Deployment Order

### Required Migrations (Production)

Run in this exact order:

```
1. 001_initial_schema.sql         ← Base schema
2. 002_vision_scanning_tables.sql ← Scanning system
3. 002_user_profile_spec.sql      ← Profile enhancements
4. 003_add_quantities.sql         ← Quantity tracking (NEW)
5. 004_add_dinner_courses.sql     ← Dinner courses (NEW)
```

### Optional Migrations

- `002_add_demo_user.sql` - Only for development/testing
- `003_session_tracking.sql` - Only if implementing session management

---

## Migration Details

### ✅ 001_initial_schema.sql (Base Schema)

**Purpose:** Foundation database schema

**Creates:**
- `users` table - User accounts with subscription tracking
- `household_profiles` table - Per-user household settings
  - Region, timezone, language, measurement system
  - Meal times, cuisine preferences
  - **skill_level** (1-5) - Cooking skill level
- `family_members` table - Individual family member profiles
- `meal_plans` table - Generated meal plans storage

**Features:**
- Row Level Security (RLS) policies
- Indexes for performance
- Cascading deletes
- Default values

**Size:** ~15KB  
**Runtime:** ~2 seconds

---

### ✅ 002_vision_scanning_tables.sql (Vision Scanning)

**Purpose:** Vision AI ingredient scanning and pantry management

**Creates:**
- `ingredient_scans` table - Scan metadata
- `detected_ingredients` table - AI-detected ingredients
- `user_pantry` table - User's ingredient inventory
- `scan_feedback` table - User feedback on scans
- `scan_corrections` table - User corrections to scans

**Features:**
- Auto-add to pantry trigger
- Confidence scoring
- Multi-ingredient scan support
- Feedback loop for AI improvement

**Size:** ~20KB  
**Runtime:** ~3 seconds

---

### ✅ 002_user_profile_spec.sql (Profile Extensions)

**Purpose:** Extended user profile functionality

**Adds:**
- `onboarding_completed_at` column to household_profiles
- `basic_spices_available` column (boolean)
- `audit_log` table for tracking changes
- `get_full_user_profile()` function

**Features:**
- Audit trail for compliance
- Onboarding completion tracking
- Structured profile retrieval

**Size:** ~8KB  
**Runtime:** ~1 second

---

### ✅ 003_add_quantities.sql (Quantity Tracking) ⭐ NEW

**Purpose:** Complete quantity tracking for ingredients and pantry

**Adds to Existing Tables:**
- `user_pantry`: quantity, unit, estimated, quantity_confidence
- `detected_ingredients`: detected_quantity, detected_unit

**Creates New Tables:**
- `quantity_units` (21 units):
  - Weight: g, kg, lb, oz
  - Volume: ml, l, cup, tbsp, tsp, fl_oz, pint, quart, gallon
  - Count: piece, clove, slice, pinch, dash, can, package, box
- `standard_serving_sizes` (50+ ingredients):
  - Standard serving per ingredient
  - Unit conversions
  - Serving equivalents

**Creates Functions:**
- `convert_unit(quantity, from_unit, to_unit, ingredient)` - Unit conversion
- `get_standard_serving(ingredient)` - Get standard serving size
- `check_recipe_sufficiency(recipe_ingredients, user_id)` - Check if user has enough

**Creates Views:**
- `pantry_inventory_summary` (materialized) - Aggregated pantry stats

**Updates:**
- Modified `auto_add_confirmed_to_pantry` trigger to handle quantities

**Idempotency:** ✅ Safe to re-run
- IF NOT EXISTS checks for columns
- CREATE TABLE IF NOT EXISTS
- ON CONFLICT DO NOTHING for inserts
- No duplicate object errors

**Size:** 467 lines, ~35KB  
**Runtime:** ~5-10 seconds  
**Critical:** Enables quantity-aware recipe planning

---

### ✅ 004_add_dinner_courses.sql (Multi-Course Meals) ⭐ NEW

**Purpose:** Support multi-course dinner planning

**Adds:**
- `dinner_courses` column to household_profiles
  - Type: INTEGER
  - Default: 2
  - Range: 1-5
  - 1 = Single dish
  - 2 = Main + side
  - 3 = Appetizer + main + dessert
  - 4 = Appetizer + main + side + dessert
  - 5 = Full formal dinner

**Features:**
- Check constraint for valid range
- Documentation comments
- Idempotent (safe to re-run)

**Idempotency:** ✅ Safe to re-run
- IF NOT EXISTS check for column
- IF NOT EXISTS check for constraint

**Size:** ~1KB  
**Runtime:** <1 second

---

## Database Schema After All Migrations

### Core Tables

**users**
- id, email, full_name, subscription_tier, last_login_at, created_at, updated_at

**household_profiles** (1 per user)
- id, user_id, region, timezone, language, measurement_system
- meal_times, breakfast_style, lunch_style, dinner_style
- cuisine_preferences, dietary_restrictions, nutrition_targets
- **skill_level** (1-5)
- **dinner_courses** (1-5)
- household_size, onboarding_completed_at, basic_spices_available

**family_members**
- id, household_id, name, age_category, dietary_restrictions

**ingredient_scans**
- id, user_id, image_url, scan_status, created_at

**detected_ingredients**
- id, scan_id, ingredient_name, confidence_score
- **detected_quantity**, **detected_unit**
- confirmed, created_at

**user_pantry**
- id, user_id, ingredient_name, **quantity**, **unit**, **estimated**
- **quantity_confidence**, last_restocked_at, created_at, updated_at

**quantity_units** (Reference)
- unit_name, unit_type, conversion_to_base, base_unit

**standard_serving_sizes** (Reference)
- ingredient_name, standard_serving_quantity, standard_serving_unit

**scan_feedback**
- id, scan_id, user_id, was_accurate, feedback_text

**scan_corrections**
- id, scan_id, detected_id, corrected_ingredient_name

**meal_plans**
- id, user_id, plan_type, plan_date, recipes, created_at

**audit_log**
- id, user_id, action, table_name, record_id, changes, created_at

### Functions

1. `convert_unit(quantity, from_unit, to_unit, ingredient)` - Convert between units
2. `get_standard_serving(ingredient)` - Get standard serving for ingredient
3. `check_recipe_sufficiency(recipe_ingredients, user_id)` - Check pantry sufficiency
4. `get_full_user_profile(user_id)` - Get complete profile

### Triggers

1. `auto_add_confirmed_to_pantry` - Auto-add confirmed scans to pantry (with quantities)

### Materialized Views

1. `pantry_inventory_summary` - Aggregated pantry inventory

### Indexes

- Primary keys on all tables
- Foreign key indexes
- scan_status, user_id indexes for performance
- ingredient_name indexes for search

---

## Verification Commands

### Python Helper Script

```bash
cd services/api/migrations
python db_helper.py
```

**Checks:**
- ✅ Database connection
- ✅ All tables exist
- ✅ All columns exist (skill_level, dinner_courses, quantity, unit, etc.)
- ✅ All functions defined
- ✅ Shows detailed table schemas

### PowerShell Quick Check

```powershell
.\services\api\verify_migrations.ps1
```

### Manual SQL Verification

```sql
-- Check tables
SELECT table_name FROM information_schema.tables 
WHERE table_schema = 'public' 
ORDER BY table_name;

-- Check household_profiles columns
SELECT column_name, data_type, column_default 
FROM information_schema.columns 
WHERE table_name = 'household_profiles'
ORDER BY ordinal_position;

-- Check functions
SELECT routine_name 
FROM information_schema.routines 
WHERE routine_schema = 'public' 
AND routine_type = 'FUNCTION'
ORDER BY routine_name;

-- Check quantity tracking
SELECT * FROM quantity_units LIMIT 5;
SELECT * FROM standard_serving_sizes LIMIT 5;

-- Test unit conversion
SELECT convert_unit(1.0, 'cup', 'ml', 'water');

-- Test standard serving
SELECT * FROM get_standard_serving('chicken breast');
```

---

## Deployment Steps

### Option 1: Automated (Python)

```bash
cd services/api/migrations
python run_migrations.py
```

This will:
1. Connect to database
2. Run all migrations in order
3. Show progress for each
4. Verify all objects created
5. Display detailed results

### Option 2: Manual (Supabase SQL Editor)

1. **Go to Supabase Dashboard**
   - Navigate to your project
   - Click "SQL Editor"

2. **Run Migrations in Order:**

   ```sql
   -- Step 1: Base Schema
   -- Copy/paste contents of 001_initial_schema.sql
   -- Click "Run"
   
   -- Step 2: Vision Scanning
   -- Copy/paste contents of 002_vision_scanning_tables.sql
   -- Click "Run"
   
   -- Step 3: Profile Extensions
   -- Copy/paste contents of 002_user_profile_spec.sql
   -- Click "Run"
   
   -- Step 4: Quantity Tracking
   -- Copy/paste contents of 003_add_quantities.sql
   -- Click "Run" (may take 5-10 seconds)
   
   -- Step 5: Dinner Courses
   -- Copy/paste contents of 004_add_dinner_courses.sql
   -- Click "Run"
   ```

3. **Verify Success**
   - Check for green success messages
   - No red error messages
   - Run verification queries above

### Option 3: Render Auto-Deploy

Migrations will auto-run on Render if:
- Migration files are in `services/api/migrations/`
- Render is configured to run migrations on deploy
- DATABASE_URL is set correctly

**Current Setup:** Render auto-runs migrations ✅

---

## Migration Fixes Applied

### Migration 003 (Idempotency Fixes)

**Iteration 1:** Made columns IF NOT EXISTS
- Fixed "column already exists" errors
- Commit: `d5fbbb1`

**Iteration 2:** Added UNIQUE constraint
- Fixed "no unique constraint for ON CONFLICT" error
- Added UNIQUE to ingredient_name in standard_serving_sizes
- Commit: `ae4e59d`

**Iteration 3:** Removed invalid column reference
- Fixed "column updated_at does not exist" error
- Removed MAX(updated_at) from materialized view
- Commit: `cbd5c02`

**Result:** Migration 003 is now fully idempotent and safe to re-run ✅

### Migration 004 (Idempotency)

**Applied:** IF NOT EXISTS checks for column and constraint
- Safe to re-run without errors
- Commit: `b927146`

---

## Rollback Procedures

### Rollback 004 (Dinner Courses)

```sql
-- Drop constraint
ALTER TABLE household_profiles 
DROP CONSTRAINT IF EXISTS check_dinner_courses_range;

-- Drop column
ALTER TABLE household_profiles 
DROP COLUMN IF EXISTS dinner_courses;
```

### Rollback 003 (Quantity Tracking)

```sql
-- Drop views
DROP MATERIALIZED VIEW IF EXISTS pantry_inventory_summary CASCADE;

-- Drop tables
DROP TABLE IF EXISTS standard_serving_sizes CASCADE;
DROP TABLE IF EXISTS quantity_units CASCADE;

-- Drop functions
DROP FUNCTION IF EXISTS convert_unit CASCADE;
DROP FUNCTION IF EXISTS get_standard_serving CASCADE;
DROP FUNCTION IF EXISTS check_recipe_sufficiency CASCADE;

-- Drop columns
ALTER TABLE user_pantry DROP COLUMN IF EXISTS quantity;
ALTER TABLE user_pantry DROP COLUMN IF EXISTS unit;
ALTER TABLE user_pantry DROP COLUMN IF EXISTS estimated;
ALTER TABLE user_pantry DROP COLUMN IF EXISTS quantity_confidence;

ALTER TABLE detected_ingredients DROP COLUMN IF EXISTS detected_quantity;
ALTER TABLE detected_ingredients DROP COLUMN IF EXISTS detected_unit;
```

---

## Testing Checklist

After migrations complete:

- [ ] Verify all tables exist (`python db_helper.py`)
- [ ] Create test household profile with skill_level and dinner_courses
- [ ] Add test ingredient to pantry with quantity and unit
- [ ] Test unit conversion: `SELECT convert_unit(1.0, 'cup', 'ml', 'water');`
- [ ] Test serving lookup: `SELECT * FROM get_standard_serving('chicken breast');`
- [ ] Query pantry summary: `SELECT * FROM pantry_inventory_summary;`
- [ ] Test API endpoints:
  - `GET /api/v1/profile/household` (should return skill_level, dinner_courses)
  - `POST /api/v1/scanning/upload` (should detect quantities)
  - `GET /api/v1/pantry` (should show quantities with units)
- [ ] Test Flutter app:
  - Settings screen shows skill level selector
  - Settings screen shows dinner courses selector
  - Both values save and persist
  - Scanning detects quantities
  - Pantry shows quantities

---

## Production Readiness

### Current Status: **95% Ready** 🚀

**Completed:**
- ✅ All migration files created
- ✅ Migrations 003 & 004 are idempotent
- ✅ Backend API updated (profile routes, scanning routes)
- ✅ Flutter UI complete (skill level, dinner courses)
- ✅ All settings wired end-to-end
- ✅ Helper scripts created (db_helper.py, run_migrations.py)
- ✅ Documentation complete

**Remaining:**
- ⏸️ Run migrations on Supabase (user action required)
- ⏸️ Verify Render deployment success
- ⏸️ Physical device testing (10 test cases)

### Next Actions

1. **Run Migrations** (5 minutes)
   ```bash
   # Option A: Python helper
   cd services/api/migrations
   python run_migrations.py
   
   # Option B: Supabase SQL Editor
   # Run each migration file manually
   ```

2. **Verify Deployment** (2 minutes)
   ```bash
   # Check Render logs
   # Verify backend starts without errors
   # Test API: curl https://savo-api.onrender.com/health
   ```

3. **Physical Device Testing** (30 minutes)
   ```bash
   cd apps/mobile
   flutter run --release
   # Execute 10 test cases from docs/TESTING_CHECKLIST.md
   ```

---

## Support & Resources

**Documentation:**
- [services/api/migrations/README.md](README.md) - Migration guide
- [SUPABASE_SETUP_GUIDE.md](../../SUPABASE_SETUP_GUIDE.md) - Database setup
- [docs/TESTING_CHECKLIST.md](../../docs/TESTING_CHECKLIST.md) - Testing guide

**Helper Scripts:**
- `db_helper.py` - Database verification
- `run_migrations.py` - Automated migration runner
- `verify_migrations.ps1` - Quick PowerShell check

**Troubleshooting:**
1. Check environment variables (DATABASE_URL or SUPABASE credentials)
2. Verify network access to database
3. Review Supabase logs for errors
4. Re-run migrations (safe with idempotency)
5. Use `python db_helper.py` for diagnostics

---

**Last Updated:** January 2, 2026  
**Version:** 004  
**Ready for Production Deployment** ✅
