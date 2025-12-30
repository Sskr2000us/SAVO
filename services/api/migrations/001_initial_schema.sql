-- SAVO Database Schema - Initial Migration
-- Created: 2025-12-30
-- Purpose: Core tables for user profiles, family members, inventory, and meal planning

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- USERS AND AUTHENTICATION
-- ============================================================================

-- Users table (extends Supabase auth.users)
CREATE TABLE public.users (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT UNIQUE NOT NULL,
    full_name TEXT,
    phone TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_login_at TIMESTAMPTZ,
    is_active BOOLEAN DEFAULT true,
    subscription_tier TEXT DEFAULT 'free' CHECK (subscription_tier IN ('free', 'premium', 'family', 'lifetime')),
    subscription_expires_at TIMESTAMPTZ
);

-- ============================================================================
-- HOUSEHOLD AND FAMILY PROFILES
-- ============================================================================

-- Household profiles (one per user/family)
CREATE TABLE public.household_profiles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    
    -- Regional settings
    region TEXT DEFAULT 'US',
    culture TEXT DEFAULT 'western',
    primary_language TEXT DEFAULT 'en-US',
    measurement_system TEXT DEFAULT 'imperial' CHECK (measurement_system IN ('metric', 'imperial')),
    timezone TEXT DEFAULT 'UTC',
    
    -- Meal times (JSON format)
    meal_times JSONB DEFAULT '{
        "breakfast": "07:00-09:00",
        "lunch": "12:00-14:00",
        "dinner": "18:00-21:00"
    }'::jsonb,
    
    -- Meal preferences (JSON format)
    breakfast_preferences JSONB DEFAULT '[]'::jsonb,
    lunch_preferences JSONB DEFAULT '[]'::jsonb,
    dinner_preferences JSONB DEFAULT '[]'::jsonb,
    
    -- Cuisine preferences
    favorite_cuisines TEXT[] DEFAULT ARRAY['Italian', 'American'],
    avoided_cuisines TEXT[] DEFAULT ARRAY[]::TEXT[],
    
    -- Nutrition targets (JSON format)
    nutrition_targets JSONB DEFAULT '{
        "daily_calories": 2200,
        "protein_g": 120,
        "carbs_g": 250,
        "fat_g": 70,
        "sodium_mg": 2300,
        "sugar_g": 50,
        "fiber_g": 30
    }'::jsonb,
    
    -- Skill tracking
    skill_level INTEGER DEFAULT 2 CHECK (skill_level BETWEEN 1 AND 5),
    confidence_score DECIMAL(3,2) DEFAULT 0.70 CHECK (confidence_score BETWEEN 0 AND 1),
    recipes_completed INTEGER DEFAULT 0,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT unique_user_household UNIQUE(user_id)
);

-- Family members table
CREATE TABLE public.family_members (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    household_id UUID NOT NULL REFERENCES public.household_profiles(id) ON DELETE CASCADE,
    
    -- Basic info
    name TEXT NOT NULL,
    age INTEGER NOT NULL CHECK (age >= 0 AND age <= 120),
    age_category TEXT NOT NULL CHECK (age_category IN ('child', 'teen', 'adult', 'senior')),
    
    -- Dietary restrictions
    dietary_restrictions TEXT[] DEFAULT ARRAY[]::TEXT[],
    allergens TEXT[] DEFAULT ARRAY[]::TEXT[],
    food_preferences TEXT[] DEFAULT ARRAY[]::TEXT[],
    food_dislikes TEXT[] DEFAULT ARRAY[]::TEXT[],
    
    -- Health conditions
    health_conditions TEXT[] DEFAULT ARRAY[]::TEXT[],
    medical_dietary_needs TEXT[] DEFAULT ARRAY[]::TEXT[],
    
    -- Preferences
    spice_tolerance TEXT DEFAULT 'medium' CHECK (spice_tolerance IN ('none', 'mild', 'medium', 'high', 'very_high')),
    
    -- Order for display
    display_order INTEGER DEFAULT 0,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- INVENTORY MANAGEMENT
-- ============================================================================

-- Inventory items table
CREATE TABLE public.inventory_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    
    -- Item identification
    canonical_name TEXT NOT NULL,
    display_name TEXT NOT NULL,
    category TEXT,
    
    -- Quantity tracking
    quantity DECIMAL(10,2) NOT NULL DEFAULT 1,
    unit TEXT NOT NULL DEFAULT 'pcs',
    
    -- Storage info
    storage_location TEXT DEFAULT 'pantry' CHECK (storage_location IN ('pantry', 'fridge', 'freezer', 'counter')),
    item_state TEXT DEFAULT 'raw' CHECK (item_state IN ('raw', 'cooked', 'prepared')),
    
    -- Freshness tracking
    purchase_date DATE,
    expiry_date DATE,
    freshness_days_remaining INTEGER,
    is_low_stock BOOLEAN DEFAULT false,
    low_stock_threshold DECIMAL(10,2) DEFAULT 1.0,
    
    -- Source tracking
    source TEXT DEFAULT 'manual' CHECK (source IN ('manual', 'scan', 'import')),
    scan_confidence DECIMAL(3,2) CHECK (scan_confidence BETWEEN 0 AND 1),
    
    -- Notes
    notes TEXT,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_used_at TIMESTAMPTZ,
    
    CONSTRAINT positive_quantity CHECK (quantity >= 0)
);

-- Inventory usage history
CREATE TABLE public.inventory_usage (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    inventory_item_id UUID NOT NULL REFERENCES public.inventory_items(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    
    -- Usage details
    quantity_used DECIMAL(10,2) NOT NULL,
    unit TEXT NOT NULL,
    recipe_id UUID, -- Reference to recipe/meal plan
    usage_type TEXT DEFAULT 'recipe' CHECK (usage_type IN ('recipe', 'manual', 'expired', 'discarded')),
    
    -- Timestamps
    used_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT positive_quantity_used CHECK (quantity_used > 0)
);

-- ============================================================================
-- MEAL PLANNING AND RECIPES
-- ============================================================================

-- Meal plans table
CREATE TABLE public.meal_plans (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    household_id UUID REFERENCES public.household_profiles(id) ON DELETE SET NULL,
    
    -- Plan details
    plan_type TEXT NOT NULL CHECK (plan_type IN ('daily', 'weekly', 'party')),
    plan_date DATE NOT NULL,
    meal_type TEXT CHECK (meal_type IN ('breakfast', 'lunch', 'dinner', 'snack', 'any')),
    
    -- Cuisine and preferences
    selected_cuisine TEXT,
    servings INTEGER NOT NULL DEFAULT 4,
    time_available_minutes INTEGER,
    
    -- Plan data (JSON format)
    recipes JSONB NOT NULL DEFAULT '[]'::jsonb,
    selected_recipe_id TEXT, -- Which recipe user chose
    
    -- Status
    status TEXT DEFAULT 'planned' CHECK (status IN ('planned', 'cooking', 'completed', 'skipped', 'abandoned')),
    completion_rating INTEGER CHECK (completion_rating BETWEEN 1 AND 5),
    completion_notes TEXT,
    
    -- Timestamps
    planned_at TIMESTAMPTZ DEFAULT NOW(),
    started_cooking_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Recipe history (tracks completed recipes for variety)
CREATE TABLE public.recipe_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    meal_plan_id UUID REFERENCES public.meal_plans(id) ON DELETE SET NULL,
    
    -- Recipe details
    recipe_name TEXT NOT NULL,
    cuisine TEXT,
    difficulty_level INTEGER CHECK (difficulty_level BETWEEN 1 AND 5),
    estimated_time_minutes INTEGER,
    
    -- Completion tracking
    completed_at TIMESTAMPTZ DEFAULT NOW(),
    was_successful BOOLEAN DEFAULT true,
    user_rating INTEGER CHECK (user_rating BETWEEN 1 AND 5),
    user_notes TEXT,
    
    -- Intelligence data
    health_fit_score DECIMAL(3,2) CHECK (health_fit_score BETWEEN 0 AND 1),
    skill_fit_category TEXT CHECK (skill_fit_category IN ('perfect', 'stretch', 'too_easy', 'too_hard')),
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- INDEXES FOR PERFORMANCE
-- ============================================================================

-- Users indexes
CREATE INDEX idx_users_email ON public.users(email);
CREATE INDEX idx_users_active ON public.users(is_active);

-- Household profiles indexes
CREATE INDEX idx_household_user ON public.household_profiles(user_id);

-- Family members indexes
CREATE INDEX idx_family_household ON public.family_members(household_id);
CREATE INDEX idx_family_display_order ON public.family_members(household_id, display_order);

-- Inventory indexes
CREATE INDEX idx_inventory_user ON public.inventory_items(user_id);
CREATE INDEX idx_inventory_category ON public.inventory_items(user_id, category);
CREATE INDEX idx_inventory_low_stock ON public.inventory_items(user_id, is_low_stock) WHERE is_low_stock = true;
CREATE INDEX idx_inventory_expiry ON public.inventory_items(user_id, expiry_date) WHERE expiry_date IS NOT NULL;
CREATE INDEX idx_inventory_updated ON public.inventory_items(user_id, updated_at DESC);

-- Inventory usage indexes
CREATE INDEX idx_usage_item ON public.inventory_usage(inventory_item_id);
CREATE INDEX idx_usage_user_date ON public.inventory_usage(user_id, used_at DESC);

-- Meal plans indexes
CREATE INDEX idx_meal_plans_user_date ON public.meal_plans(user_id, plan_date DESC);
CREATE INDEX idx_meal_plans_status ON public.meal_plans(user_id, status);
CREATE INDEX idx_meal_plans_type ON public.meal_plans(user_id, plan_type, plan_date DESC);

-- Recipe history indexes
CREATE INDEX idx_recipe_history_user ON public.recipe_history(user_id, completed_at DESC);
CREATE INDEX idx_recipe_history_cuisine ON public.recipe_history(user_id, cuisine);
CREATE INDEX idx_recipe_history_rating ON public.recipe_history(user_id, user_rating);

-- ============================================================================
-- TRIGGERS FOR AUTOMATIC UPDATES
-- ============================================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply updated_at trigger to tables
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON public.users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_household_updated_at BEFORE UPDATE ON public.household_profiles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_family_updated_at BEFORE UPDATE ON public.family_members
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_inventory_updated_at BEFORE UPDATE ON public.inventory_items
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_meal_plans_updated_at BEFORE UPDATE ON public.meal_plans
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Function to check and update low stock status
CREATE OR REPLACE FUNCTION check_low_stock()
RETURNS TRIGGER AS $$
BEGIN
    NEW.is_low_stock = (NEW.quantity <= NEW.low_stock_threshold);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply low stock trigger
CREATE TRIGGER check_inventory_low_stock BEFORE INSERT OR UPDATE OF quantity, low_stock_threshold
    ON public.inventory_items
    FOR EACH ROW EXECUTE FUNCTION check_low_stock();

-- ============================================================================
-- ROW LEVEL SECURITY (RLS)
-- ============================================================================

-- Enable RLS on all tables
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.household_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.family_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.inventory_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.inventory_usage ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.meal_plans ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.recipe_history ENABLE ROW LEVEL SECURITY;

-- Users policies
CREATE POLICY "Users can view own profile" ON public.users
    FOR SELECT USING (auth.uid() = id);

CREATE POLICY "Users can update own profile" ON public.users
    FOR UPDATE USING (auth.uid() = id);

-- Household profiles policies
CREATE POLICY "Users can view own household" ON public.household_profiles
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own household" ON public.household_profiles
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own household" ON public.household_profiles
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own household" ON public.household_profiles
    FOR DELETE USING (auth.uid() = user_id);

-- Family members policies
CREATE POLICY "Users can view own family members" ON public.family_members
    FOR SELECT USING (
        household_id IN (
            SELECT id FROM public.household_profiles WHERE user_id = auth.uid()
        )
    );

CREATE POLICY "Users can insert own family members" ON public.family_members
    FOR INSERT WITH CHECK (
        household_id IN (
            SELECT id FROM public.household_profiles WHERE user_id = auth.uid()
        )
    );

CREATE POLICY "Users can update own family members" ON public.family_members
    FOR UPDATE USING (
        household_id IN (
            SELECT id FROM public.household_profiles WHERE user_id = auth.uid()
        )
    );

CREATE POLICY "Users can delete own family members" ON public.family_members
    FOR DELETE USING (
        household_id IN (
            SELECT id FROM public.household_profiles WHERE user_id = auth.uid()
        )
    );

-- Inventory items policies
CREATE POLICY "Users can view own inventory" ON public.inventory_items
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own inventory" ON public.inventory_items
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own inventory" ON public.inventory_items
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own inventory" ON public.inventory_items
    FOR DELETE USING (auth.uid() = user_id);

-- Inventory usage policies
CREATE POLICY "Users can view own inventory usage" ON public.inventory_usage
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own inventory usage" ON public.inventory_usage
    FOR INSERT WITH CHECK (auth.uid() = user_id);

-- Meal plans policies
CREATE POLICY "Users can view own meal plans" ON public.meal_plans
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own meal plans" ON public.meal_plans
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own meal plans" ON public.meal_plans
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own meal plans" ON public.meal_plans
    FOR DELETE USING (auth.uid() = user_id);

-- Recipe history policies
CREATE POLICY "Users can view own recipe history" ON public.recipe_history
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own recipe history" ON public.recipe_history
    FOR INSERT WITH CHECK (auth.uid() = user_id);

-- ============================================================================
-- HELPER FUNCTIONS
-- ============================================================================

-- Function to get low stock items
CREATE OR REPLACE FUNCTION get_low_stock_items(p_user_id UUID)
RETURNS TABLE (
    item_id UUID,
    display_name TEXT,
    quantity DECIMAL,
    unit TEXT,
    low_stock_threshold DECIMAL,
    storage_location TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        id,
        inventory_items.display_name,
        inventory_items.quantity,
        inventory_items.unit,
        inventory_items.low_stock_threshold,
        inventory_items.storage_location
    FROM public.inventory_items
    WHERE user_id = p_user_id
      AND is_low_stock = true
      AND quantity > 0
    ORDER BY quantity ASC;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to get expiring soon items (within 3 days)
CREATE OR REPLACE FUNCTION get_expiring_items(p_user_id UUID, p_days INTEGER DEFAULT 3)
RETURNS TABLE (
    item_id UUID,
    display_name TEXT,
    quantity DECIMAL,
    unit TEXT,
    expiry_date DATE,
    days_until_expiry INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        id,
        inventory_items.display_name,
        inventory_items.quantity,
        inventory_items.unit,
        inventory_items.expiry_date,
        (inventory_items.expiry_date - CURRENT_DATE)::INTEGER AS days_until_expiry
    FROM public.inventory_items
    WHERE user_id = p_user_id
      AND expiry_date IS NOT NULL
      AND expiry_date <= CURRENT_DATE + p_days
      AND quantity > 0
    ORDER BY expiry_date ASC;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to deduct inventory after recipe selection
CREATE OR REPLACE FUNCTION deduct_inventory_for_recipe(
    p_user_id UUID,
    p_meal_plan_id UUID,
    p_ingredients JSONB
)
RETURNS TABLE (
    success BOOLEAN,
    message TEXT,
    insufficient_items JSONB
) AS $$
DECLARE
    v_ingredient JSONB;
    v_item_name TEXT;
    v_quantity_needed DECIMAL;
    v_unit TEXT;
    v_inventory_item RECORD;
    v_insufficient JSONB := '[]'::jsonb;
BEGIN
    -- Iterate through ingredients
    FOR v_ingredient IN SELECT * FROM jsonb_array_elements(p_ingredients)
    LOOP
        v_item_name := v_ingredient->>'name';
        v_quantity_needed := (v_ingredient->>'quantity')::DECIMAL;
        v_unit := v_ingredient->>'unit';
        
        -- Find inventory item
        SELECT * INTO v_inventory_item
        FROM public.inventory_items
        WHERE user_id = p_user_id
          AND (canonical_name ILIKE v_item_name OR display_name ILIKE v_item_name)
          AND quantity >= v_quantity_needed
        LIMIT 1;
        
        IF NOT FOUND THEN
            -- Add to insufficient items
            v_insufficient := v_insufficient || jsonb_build_object(
                'name', v_item_name,
                'needed', v_quantity_needed,
                'unit', v_unit,
                'available', 0
            );
        ELSE
            -- Deduct quantity
            UPDATE public.inventory_items
            SET 
                quantity = quantity - v_quantity_needed,
                last_used_at = NOW()
            WHERE id = v_inventory_item.id;
            
            -- Record usage
            INSERT INTO public.inventory_usage (
                inventory_item_id,
                user_id,
                recipe_id,
                quantity_used,
                unit,
                usage_type
            ) VALUES (
                v_inventory_item.id,
                p_user_id,
                p_meal_plan_id,
                v_quantity_needed,
                v_unit,
                'recipe'
            );
        END IF;
    END LOOP;
    
    -- Return result
    IF jsonb_array_length(v_insufficient) = 0 THEN
        RETURN QUERY SELECT true, 'Inventory deducted successfully'::TEXT, '[]'::jsonb;
    ELSE
        RETURN QUERY SELECT false, 'Insufficient inventory for some items'::TEXT, v_insufficient;
    END IF;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================================================
-- INITIAL DATA (Optional)
-- ============================================================================

-- Insert default age category mappings
CREATE TABLE public.age_categories (
    category TEXT PRIMARY KEY,
    min_age INTEGER NOT NULL,
    max_age INTEGER NOT NULL,
    description TEXT
);

INSERT INTO public.age_categories (category, min_age, max_age, description) VALUES
    ('child', 0, 12, 'Children aged 0-12'),
    ('teen', 13, 17, 'Teenagers aged 13-17'),
    ('adult', 18, 64, 'Adults aged 18-64'),
    ('senior', 65, 120, 'Seniors aged 65+');

-- Grant permissions
GRANT USAGE ON SCHEMA public TO postgres, anon, authenticated, service_role;
GRANT ALL ON ALL TABLES IN SCHEMA public TO postgres, service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO authenticated;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO anon;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO postgres, authenticated, service_role;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO postgres, authenticated, service_role;
