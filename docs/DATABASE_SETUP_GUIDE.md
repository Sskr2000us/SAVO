# Complete Supabase Integration Guide

## Overview

This guide covers the complete database setup for SAVO, including:
- ✅ User profiles with one-time settings
- ✅ Family member management
- ✅ Inventory tracking with automatic deduction
- ✅ Low stock alerts
- ✅ Meal planning with recipe history
- ✅ Row-level security (RLS)

---

## Part 1: Supabase Setup (5 minutes)

### Step 1: Create Supabase Project

1. Go to https://supabase.com/dashboard
2. Click "New Project"
3. Fill in:
   - **Name**: SAVO
   - **Database Password**: (generate secure password)
   - **Region**: (choose closest to you)
4. Click "Create new project"
5. Wait 2-3 minutes for provisioning

### Step 2: Run Database Migration

1. In Supabase Dashboard, go to **SQL Editor** (left sidebar)
2. Click **New Query**
3. Open file: `services/api/migrations/001_initial_schema.sql`
4. Copy entire contents
5. Paste into SQL Editor
6. Click **Run** (or press F5)
7. You should see: ✅ "Success. No rows returned"

### Step 3: Get API Keys

1. Go to **Settings** → **API** (left sidebar)
2. Copy these values:
   - **Project URL**: `https://xxxxx.supabase.co`
   - **anon public**: `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...`
   - **service_role**: `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...` (⚠️ Keep secret!)

---

## Part 2: Backend Configuration (2 minutes)

### Step 1: Install Dependencies

```bash
cd C:\Users\sskr2\SAVO\services\api
.\.venv\Scripts\Activate.ps1
pip install supabase postgrest
```

### Step 2: Update Environment Variables

Create/update `.env` file in `services/api/`:

```env
# Existing variables
SAVO_LLM_PROVIDER=mock
SAVO_VISION_PROVIDER=mock

# NEW: Supabase configuration
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_SERVICE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

⚠️ **Security Notes:**
- `SUPABASE_ANON_KEY`: Safe to use in Flutter app (client-side)
- `SUPABASE_SERVICE_KEY`: NEVER expose to client! Backend only!

### Step 3: Update Render Dashboard (for production)

1. Go to Render Dashboard → Your Service
2. Go to **Environment** tab
3. Add new variables:
   ```
   SUPABASE_URL = https://xxxxx.supabase.co
   SUPABASE_ANON_KEY = eyJhbGci...
   SUPABASE_SERVICE_KEY = eyJhbGci...
   ```
4. Click **Save Changes**
5. Service will auto-deploy

---

## Part 3: Testing the Database (10 minutes)

### Test 1: Start Local Server

```powershell
cd C:\Users\sskr2\SAVO\services\api
.\.venv\Scripts\Activate.ps1
$env:SAVO_LLM_PROVIDER="mock"
uvicorn app.main:app --reload --port 8000
```

Open: http://localhost:8000/docs

### Test 2: Create Household Profile

**Endpoint:** `POST /profile/household`

**Headers:**
```json
{
  "x-user-id": "test-user-123",
  "x-user-email": "test@example.com"
}
```

**Request Body:**
```json
{
  "region": "US",
  "culture": "western",
  "primary_language": "en-US",
  "measurement_system": "imperial",
  "timezone": "America/New_York",
  "favorite_cuisines": ["Italian", "Mexican", "Indian"],
  "nutrition_targets": {
    "daily_calories": 2200,
    "protein_g": 120,
    "carbs_g": 250,
    "fat_g": 70
  },
  "skill_level": 2
}
```

**Expected Response:**
```json
{
  "success": true,
  "message": "Household profile created successfully",
  "profile": {
    "id": "uuid-here",
    "user_id": "test-user-123",
    "region": "US",
    ...
  }
}
```

### Test 3: Add Family Member

**Endpoint:** `POST /profile/family-members`

**Headers:**
```json
{
  "x-user-id": "test-user-123"
}
```

**Request Body:**
```json
{
  "name": "John Doe",
  "age": 35,
  "dietary_restrictions": ["vegetarian"],
  "allergens": ["peanuts", "shellfish"],
  "health_conditions": ["diabetes"],
  "spice_tolerance": "medium"
}
```

**Expected Response:**
```json
{
  "success": true,
  "message": "Family member added successfully",
  "member": {
    "id": "uuid-here",
    "name": "John Doe",
    "age": 35,
    "age_category": "adult",
    ...
  }
}
```

### Test 4: Add Inventory Items

**Endpoint:** `POST /inventory-db/items`

**Headers:**
```json
{
  "x-user-id": "test-user-123"
}
```

**Request Body:**
```json
{
  "canonical_name": "tomato",
  "display_name": "Fresh Tomatoes",
  "category": "vegetables",
  "quantity": 5,
  "unit": "pcs",
  "storage_location": "counter",
  "low_stock_threshold": 2,
  "expiry_date": "2025-01-05"
}
```

**Expected Response:**
```json
{
  "success": true,
  "message": "Item added to inventory",
  "item": {
    "id": "uuid-here",
    "canonical_name": "tomato",
    "quantity": 5,
    "is_low_stock": false,
    ...
  }
}
```

### Test 5: Check Low Stock Alerts

**Endpoint:** `GET /inventory-db/alerts/low-stock`

**Headers:**
```json
{
  "x-user-id": "test-user-123"
}
```

### Test 6: Deduct Inventory After Recipe Selection

**Endpoint:** `POST /inventory-db/deduct`

**Headers:**
```json
{
  "x-user-id": "test-user-123"
}
```

**Request Body:**
```json
{
  "meal_plan_id": "test-meal-plan-123",
  "ingredients": [
    {"name": "tomato", "quantity": 3, "unit": "pcs"},
    {"name": "pasta", "quantity": 200, "unit": "g"}
  ]
}
```

**Expected Response:**
```json
{
  "success": true,
  "message": "Inventory deducted successfully",
  "ingredients_used": 2,
  "low_stock_alerts": {
    "count": 1,
    "items": [
      {
        "item_id": "uuid",
        "display_name": "Fresh Tomatoes",
        "quantity": 2,
        "unit": "pcs",
        "low_stock_threshold": 2
      }
    ]
  }
}
```

---

## Part 4: API Endpoints Reference

### Profile Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/profile/household` | Get household profile |
| POST | `/profile/household` | Create household (one-time) |
| PATCH | `/profile/household` | Update household settings |
| GET | `/profile/family-members` | List all family members |
| POST | `/profile/family-members` | Add family member |
| PATCH | `/profile/family-members/{id}` | Update family member |
| DELETE | `/profile/family-members/{id}` | Remove family member |

### Inventory Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/inventory-db/items` | List all items |
| POST | `/inventory-db/items` | Add item |
| PATCH | `/inventory-db/items/{id}` | Update item |
| DELETE | `/inventory-db/items/{id}` | Remove item |
| GET | `/inventory-db/alerts/low-stock` | Get low stock alerts |
| GET | `/inventory-db/alerts/expiring?days=3` | Get expiring items |
| GET | `/inventory-db/summary` | Get full summary |
| POST | `/inventory-db/deduct` | Deduct for recipe |
| POST | `/inventory-db/manual-adjustment` | Manual adjustment |

---

## Part 5: Flutter Integration

### Step 1: Add Supabase Package

In `apps/mobile/pubspec.yaml`:

```yaml
dependencies:
  supabase_flutter: ^2.0.0
```

Run:
```bash
cd apps/mobile
flutter pub get
```

### Step 2: Initialize Supabase

In `lib/main.dart`:

```dart
import 'package:supabase_flutter/supabase_flutter.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  
  await Supabase.initialize(
    url: 'https://xxxxx.supabase.co',
    anonKey: 'your-anon-key-here',
  );
  
  runApp(MyApp());
}
```

### Step 3: Use Database in Settings Screen

Update `lib/screens/settings_screen.dart`:

```dart
import 'package:supabase_flutter/supabase_flutter.dart';

final supabase = Supabase.instance.client;

// Save household profile
Future<void> saveHouseholdProfile(Map<String, dynamic> profile) async {
  final userId = supabase.auth.currentUser?.id;
  if (userId == null) throw Exception('Not authenticated');
  
  // Create or update profile
  final response = await supabase
    .from('household_profiles')
    .upsert({
      'user_id': userId,
      ...profile,
    })
    .select()
    .single();
  
  print('Profile saved: $response');
}

// Load household profile
Future<Map<String, dynamic>?> loadHouseholdProfile() async {
  final userId = supabase.auth.currentUser?.id;
  if (userId == null) return null;
  
  final response = await supabase
    .from('household_profiles')
    .select()
    .eq('user_id', userId)
    .maybeSingle();
  
  return response;
}

// Save family member
Future<void> saveFamilyMember(Map<String, dynamic> member) async {
  final userId = supabase.auth.currentUser?.id;
  if (userId == null) throw Exception('Not authenticated');
  
  // Get household ID
  final household = await loadHouseholdProfile();
  if (household == null) throw Exception('Create household first');
  
  await supabase.from('family_members').insert({
    'household_id': household['id'],
    ...member,
  });
}
```

---

## Part 6: Automatic Inventory Deduction Flow

### How It Works

1. **User Creates Meal Plan:**
   ```
   POST /plan/daily
   → Creates meal_plans record
   → Returns recipes with ingredients
   ```

2. **User Selects Recipe:**
   ```
   POST /inventory-db/deduct
   {
     "meal_plan_id": "uuid",
     "ingredients": [...]
   }
   ```

3. **Database Function Executes:**
   ```sql
   deduct_inventory_for_recipe()
   → Checks if items exist
   → Deducts quantities
   → Records usage history
   → Triggers low stock alerts
   ```

4. **Frontend Receives Alerts:**
   ```json
   {
     "success": true,
     "low_stock_alerts": {
       "count": 2,
       "items": [...]
     }
   }
   ```

5. **Display Alert to User:**
   ```dart
   if (response['low_stock_alerts']['count'] > 0) {
     showLowStockSnackBar(context, response['low_stock_alerts']);
   }
   ```

---

## Part 7: Data Flow Diagram

```
┌─────────────────────────────────────────────────────────┐
│                    USER JOURNEY                         │
└─────────────────────────────────────────────────────────┘

1. FIRST-TIME SETUP (One-time)
   ┌─────────────────┐
   │ Flutter App     │
   │ Settings Screen │
   └────────┬────────┘
            │ POST /profile/household
            ↓
   ┌─────────────────┐
   │ Backend API     │
   └────────┬────────┘
            │ INSERT INTO household_profiles
            ↓
   ┌─────────────────┐
   │ Supabase DB     │
   │ ✅ Profile saved │
   └─────────────────┘

2. ADD FAMILY MEMBERS (One-time per member)
   ┌─────────────────┐
   │ Flutter App     │
   └────────┬────────┘
            │ POST /profile/family-members
            ↓
   ┌─────────────────┐
   │ Backend API     │
   └────────┬────────┘
            │ INSERT INTO family_members
            ↓
   ┌─────────────────┐
   │ Supabase DB     │
   │ ✅ Members saved │
   └─────────────────┘

3. SCAN INVENTORY (Ongoing)
   ┌─────────────────┐
   │ Flutter App     │
   │ Camera Scan     │
   └────────┬────────┘
            │ POST /inventory/scan
            ↓
   ┌─────────────────┐
   │ Vision AI       │
   │ (OpenAI/Google) │
   └────────┬────────┘
            │ Detected items
            ↓
   ┌─────────────────┐
   │ Backend API     │
   └────────┬────────┘
            │ POST /inventory-db/items
            ↓
   ┌─────────────────┐
   │ Supabase DB     │
   │ ✅ Items added   │
   └─────────────────┘

4. CREATE MEAL PLAN (Daily)
   ┌─────────────────┐
   │ Flutter App     │
   └────────┬────────┘
            │ POST /plan/daily
            ↓
   ┌─────────────────┐
   │ Backend API     │
   │ + Intelligence  │
   └────────┬────────┘
            │ Read: household_profiles, family_members, inventory_items
            │ Read: recipe_history (for variety)
            │
            │ Generate recipes with:
            │  • Nutrition scoring
            │  • Skill matching
            │  • Cuisine ranking
            │  • Available ingredients
            ↓
   ┌─────────────────┐
   │ INSERT INTO     │
   │ meal_plans      │
   └─────────────────┘

5. SELECT RECIPE (User picks one)
   ┌─────────────────┐
   │ Flutter App     │
   │ User taps recipe│
   └────────┬────────┘
            │ POST /inventory-db/deduct
            │ {meal_plan_id, ingredients}
            ↓
   ┌─────────────────┐
   │ Backend API     │
   └────────┬────────┘
            │ CALL deduct_inventory_for_recipe()
            ↓
   ┌─────────────────────────────────────┐
   │ Supabase DB (Atomic Transaction)    │
   │ 1. Check quantities available        │
   │ 2. UPDATE inventory_items (deduct)  │
   │ 3. INSERT INTO inventory_usage      │
   │ 4. Trigger: check_low_stock()       │
   │ 5. COMMIT                           │
   └─────────────────┬───────────────────┘
            │ Return: success + low_stock_alerts
            ↓
   ┌─────────────────┐
   │ Flutter App     │
   │ Show alerts     │
   │ Navigate to     │
   │ cooking view    │
   └─────────────────┘

6. COMPLETE RECIPE (After cooking)
   ┌─────────────────┐
   │ Flutter App     │
   │ Rate & Complete │
   └────────┬────────┘
            │ PATCH /plan/{id}/complete
            ↓
   ┌─────────────────┐
   │ Backend API     │
   └────────┬────────┘
            │ UPDATE meal_plans (status=completed)
            │ INSERT INTO recipe_history
            │ UPDATE household_profiles (recipes_completed++)
            │ TRIGGER: Calculate new skill level
            ↓
   ┌─────────────────┐
   │ Supabase DB     │
   │ ✅ Progression  │
   └─────────────────┘
```

---

## Part 8: Database Schema Visual

```
┌──────────────────────┐
│ auth.users           │ (Supabase Auth)
│ • id (PK)            │
│ • email              │
└──────────┬───────────┘
           │ 1:1
           ↓
┌──────────────────────┐
│ users                │
│ • id (PK, FK)        │
│ • email              │
│ • full_name          │
│ • subscription_tier  │
└──────────┬───────────┘
           │ 1:1
           ↓
┌──────────────────────────────┐
│ household_profiles           │
│ • id (PK)                    │
│ • user_id (FK, UNIQUE)       │
│ • region, timezone           │
│ • favorite_cuisines[]        │
│ • nutrition_targets (JSON)   │
│ • skill_level, confidence    │
│ • recipes_completed          │
└──────────┬───────────────────┘
           │ 1:N
           ↓
┌──────────────────────────────┐
│ family_members               │
│ • id (PK)                    │
│ • household_id (FK)          │
│ • name, age, age_category    │
│ • dietary_restrictions[]     │
│ • allergens[]                │
│ • health_conditions[]        │
│ • spice_tolerance            │
└──────────────────────────────┘

┌──────────────────────────────┐
│ inventory_items              │
│ • id (PK)                    │
│ • user_id (FK)               │
│ • canonical_name             │
│ • quantity, unit             │
│ • storage_location           │
│ • expiry_date                │
│ • is_low_stock (auto)        │
│ • low_stock_threshold        │
└──────────┬───────────────────┘
           │ 1:N
           ↓
┌──────────────────────────────┐
│ inventory_usage              │
│ • id (PK)                    │
│ • inventory_item_id (FK)     │
│ • user_id (FK)               │
│ • recipe_id (FK optional)    │
│ • quantity_used, unit        │
│ • used_at                    │
└──────────────────────────────┘

┌──────────────────────────────┐
│ meal_plans                   │
│ • id (PK)                    │
│ • user_id (FK)               │
│ • household_id (FK)          │
│ • plan_date, meal_type       │
│ • recipes (JSON)             │
│ • selected_recipe_id         │
│ • status (planned/completed) │
└──────────┬───────────────────┘
           │ 1:N
           ↓
┌──────────────────────────────┐
│ recipe_history               │
│ • id (PK)                    │
│ • user_id (FK)               │
│ • meal_plan_id (FK)          │
│ • recipe_name, cuisine       │
│ • completed_at               │
│ • was_successful, rating     │
│ • health_fit_score           │
│ • skill_fit_category         │
└──────────────────────────────┘
```

---

## Part 9: Security & Performance

### Row Level Security (RLS)

All tables have RLS enabled. Users can only access their own data:

```sql
-- Example policy for inventory_items
CREATE POLICY "Users can view own inventory" 
ON inventory_items
FOR SELECT 
USING (auth.uid() = user_id);
```

### Indexes

Optimized queries for:
- ✅ User data retrieval
- ✅ Low stock searches
- ✅ Expiry date alerts
- ✅ Recipe history
- ✅ Meal plan filtering

### Performance Tips

1. **Batch Operations**: Use Supabase batch inserts
2. **Prepared Statements**: Prevent SQL injection
3. **Connection Pooling**: Automatic in Supabase
4. **Monitor Slow Queries**: Use Supabase Dashboard

---

## Part 10: Troubleshooting

### Issue: "Supabase client not initialized"

**Solution:**
```bash
# Check environment variables
echo $env:SUPABASE_URL
echo $env:SUPABASE_SERVICE_KEY

# Make sure they're set before starting server
```

### Issue: "Row level security policy violated"

**Solution:**
- Make sure you're passing `x-user-id` header
- Check that user exists in `users` table
- Verify RLS policies are created

### Issue: "Insufficient inventory for some items"

**Solution:**
- This is expected behavior
- Frontend should show which items are missing
- Offer to add missing items or choose different recipe

### Issue: "Low stock threshold not triggering"

**Solution:**
- Check `low_stock_threshold` is set (default 1.0)
- Trigger runs on INSERT/UPDATE automatically
- Verify: `SELECT * FROM inventory_items WHERE is_low_stock = true;`

---

## Next Steps

1. ✅ Run migration in Supabase
2. ✅ Install Python dependencies
3. ✅ Set environment variables
4. ✅ Test all endpoints locally
5. ⏳ Integrate Flutter settings screen with database
6. ⏳ Add Supabase auth to Flutter app
7. ⏳ Deploy to Render with new env vars
8. ⏳ Test end-to-end flow

---

## Support

- **Supabase Docs**: https://supabase.com/docs
- **Python Client**: https://supabase.com/docs/reference/python/introduction
- **Flutter Client**: https://supabase.com/docs/reference/dart/introduction

**Questions?** Check logs:
```bash
# Backend logs
uvicorn app.main:app --log-level debug

# Supabase logs
# Dashboard → Logs → View real-time logs
```
