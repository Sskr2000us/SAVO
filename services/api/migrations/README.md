# SAVO Database Migrations

Complete Supabase database setup for SAVO meal planning application.

## Quick Start

### 1. Create Supabase Project
```bash
# Visit https://supabase.com/dashboard
# Create new project
# Copy your project URL and anon key
```

### 2. Run Migration
```bash
# In Supabase Dashboard:
# 1. Go to SQL Editor
# 2. Create new query
# 3. Paste contents of 001_initial_schema.sql
# 4. Click "Run"
```

### 3. Set Environment Variables
```bash
# Add to your .env file or Render dashboard:
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key-here
SUPABASE_SERVICE_KEY=your-service-key-here  # For admin operations
```

## Schema Overview

### Core Tables

#### **users** (extends auth.users)
- User account information
- Subscription tier tracking
- Last login tracking

#### **household_profiles** (one per user)
- Regional settings (timezone, language, measurement system)
- Meal time preferences
- Cuisine preferences
- Nutrition targets
- Skill level tracking

#### **family_members**
- Individual family member profiles
- Age categories (child/teen/adult/senior)
- Dietary restrictions per member
- Allergens per member
- Health conditions
- Spice tolerance levels

#### **inventory_items**
- Food items in user's kitchen
- Quantity tracking with units
- Storage location (pantry/fridge/freezer)
- Expiry date tracking
- Low stock alerts
- Purchase tracking

#### **inventory_usage**
- History of ingredient usage
- Links to recipes/meal plans
- Tracks manual adjustments
- Waste tracking (expired/discarded)

#### **meal_plans**
- Daily/weekly meal plans
- Recipe selections
- Servings and timing
- Completion tracking
- User ratings

#### **recipe_history**
- Completed recipes log
- Success/failure tracking
- User ratings and notes
- Skill progression data
- Health fit scores

## Key Features

### 🔒 Row Level Security (RLS)
- All tables protected with RLS
- Users can only access their own data
- Automatic filtering based on auth.uid()

### ⚡ Automatic Triggers
- `updated_at` timestamp auto-updates
- Low stock detection on quantity changes
- Expiry date calculations

### 📊 Helper Functions

#### `get_low_stock_items(user_id)`
Returns items below threshold:
```sql
SELECT * FROM get_low_stock_items('user-uuid-here');
```

#### `get_expiring_items(user_id, days)`
Returns items expiring within X days:
```sql
SELECT * FROM get_expiring_items('user-uuid-here', 3);
```

#### `deduct_inventory_for_recipe(user_id, meal_plan_id, ingredients_json)`
Automatically deducts ingredients after recipe selection:
```sql
SELECT * FROM deduct_inventory_for_recipe(
    'user-uuid',
    'meal-plan-uuid',
    '[{"name": "tomato", "quantity": 2, "unit": "pcs"}]'::jsonb
);
```

## Database Indexes

Optimized for:
- Fast user data retrieval
- Low stock queries
- Expiry date searches
- Meal plan history
- Recipe completion tracking

## Data Flow Example

### 1. User Signs Up
```
auth.users (Supabase Auth)
    ↓
public.users (profile created)
    ↓
household_profiles (settings created)
```

### 2. Add Family Members
```
POST /profile/family-members
    ↓
family_members table (stored)
```

### 3. Scan Inventory
```
POST /inventory/scan
    ↓
inventory_items table (items added)
    ↓
Low stock trigger checks quantity
```

### 4. Create Meal Plan
```
POST /plan/daily
    ↓
meal_plans table (plan stored)
    ↓
deduct_inventory_for_recipe() called
    ↓
inventory_items (quantities reduced)
    ↓
inventory_usage (history logged)
```

### 5. Complete Recipe
```
PATCH /plan/{id}/complete
    ↓
meal_plans.status = 'completed'
    ↓
recipe_history (success logged)
    ↓
household_profiles.recipes_completed += 1
    ↓
Skill level progression calculated
```

## Rollback

If you need to rollback the migration:

```sql
-- Drop all tables in reverse order
DROP TABLE IF EXISTS public.recipe_history CASCADE;
DROP TABLE IF EXISTS public.meal_plans CASCADE;
DROP TABLE IF EXISTS public.inventory_usage CASCADE;
DROP TABLE IF EXISTS public.inventory_items CASCADE;
DROP TABLE IF EXISTS public.family_members CASCADE;
DROP TABLE IF EXISTS public.household_profiles CASCADE;
DROP TABLE IF EXISTS public.users CASCADE;
DROP TABLE IF EXISTS public.age_categories CASCADE;

-- Drop functions
DROP FUNCTION IF EXISTS deduct_inventory_for_recipe;
DROP FUNCTION IF EXISTS get_expiring_items;
DROP FUNCTION IF EXISTS get_low_stock_items;
DROP FUNCTION IF EXISTS check_low_stock;
DROP FUNCTION IF EXISTS update_updated_at_column;
```

## Testing the Database

### Test Query 1: Create User Profile
```sql
-- After authenticating, insert user profile
INSERT INTO public.users (id, email, full_name)
VALUES (auth.uid(), 'test@example.com', 'Test User');

-- Create household profile
INSERT INTO public.household_profiles (user_id, region, favorite_cuisines)
VALUES (
    auth.uid(),
    'US',
    ARRAY['Italian', 'Mexican', 'Indian']
);
```

### Test Query 2: Add Family Member
```sql
INSERT INTO public.family_members (
    household_id,
    name,
    age,
    age_category,
    dietary_restrictions,
    allergens,
    spice_tolerance
)
SELECT 
    id,
    'John Doe',
    35,
    'adult',
    ARRAY['vegetarian'],
    ARRAY['peanuts'],
    'medium'
FROM public.household_profiles
WHERE user_id = auth.uid();
```

### Test Query 3: Add Inventory Item
```sql
INSERT INTO public.inventory_items (
    user_id,
    canonical_name,
    display_name,
    category,
    quantity,
    unit,
    storage_location,
    low_stock_threshold
)
VALUES (
    auth.uid(),
    'tomato',
    'Fresh Tomatoes',
    'vegetables',
    5,
    'pcs',
    'counter',
    2
);
```

### Test Query 4: Check Low Stock
```sql
SELECT * FROM get_low_stock_items(auth.uid());
```

### Test Query 5: Deduct Inventory
```sql
-- First create a meal plan
INSERT INTO public.meal_plans (
    user_id,
    plan_type,
    plan_date,
    meal_type,
    recipes
)
VALUES (
    auth.uid(),
    'daily',
    CURRENT_DATE,
    'dinner',
    '[{"name": "Pasta", "id": "pasta-123"}]'::jsonb
)
RETURNING id;

-- Then deduct ingredients
SELECT * FROM deduct_inventory_for_recipe(
    auth.uid(),
    'meal-plan-uuid-from-above',
    '[
        {"name": "tomato", "quantity": 3, "unit": "pcs"},
        {"name": "pasta", "quantity": 200, "unit": "g"}
    ]'::jsonb
);
```

## Security Notes

1. **Never expose service_role key** - Only use in backend
2. **RLS is enforced** - Users cannot access other users' data
3. **Use anon key for client** - Safe to use in Flutter app
4. **Service key for admin** - Backend operations only

## Performance Tips

1. **Indexes are created** for common queries
2. **Use prepared statements** to prevent SQL injection
3. **Batch operations** when possible
4. **Monitor with Supabase Dashboard** - Track slow queries

## Next Steps

1. ✅ Run migration (001_initial_schema.sql)
2. 📝 Update Python backend to use Supabase
3. 📱 Update Flutter app to use Supabase client
4. 🧪 Test all CRUD operations
5. 🚀 Deploy to production

## Support

For issues or questions:
- Supabase Docs: https://supabase.com/docs
- SQL Reference: https://www.postgresql.org/docs/
