-- Inventory taxonomy reference (no tables created)
-- Purpose: Provide a canonical list of allowed (storage_location, category, subcategory)
-- for validation, exports, or lightweight testing.
--
-- Usage:
--   Run this script in Supabase SQL editor.
--   It returns rows with (storage_location, category, subcategory).
--
-- Notes:
-- - Values are normalized (lowercase, snake_case) to match app storage.
-- - Subcategory may be NULL (category only).

WITH allowed AS (
    SELECT * FROM (
        VALUES
            -- fridge
            ('fridge', 'vegetables', 'leafy'),
            ('fridge', 'vegetables', 'root'),
            ('fridge', 'vegetables', 'cruciferous'),
            ('fridge', 'vegetables', 'other'),
            ('fridge', 'fruits', 'berries'),
            ('fridge', 'fruits', 'citrus'),
            ('fridge', 'fruits', 'tropical'),
            ('fridge', 'fruits', 'other'),
            ('fridge', 'dairy', 'milk'),
            ('fridge', 'dairy', 'cheese'),
            ('fridge', 'dairy', 'yogurt'),
            ('fridge', 'dairy', 'butter'),
            ('fridge', 'dairy', 'other'),
            ('fridge', 'proteins', 'eggs'),
            ('fridge', 'proteins', 'paneer'),
            ('fridge', 'proteins', 'meat'),
            ('fridge', 'proteins', 'fish'),
            ('fridge', 'proteins', 'other'),
            ('fridge', 'condiments', 'sauces'),
            ('fridge', 'condiments', 'pickles'),
            ('fridge', 'condiments', 'spreads'),
            ('fridge', 'condiments', 'other'),
            ('fridge', 'beverages', 'juice'),
            ('fridge', 'beverages', 'soft_drinks'),
            ('fridge', 'beverages', 'other'),
            ('fridge', 'leftovers', 'cooked'),
            ('fridge', 'leftovers', 'prepared'),
            ('fridge', 'leftovers', 'other'),

            -- pantry
            ('pantry', 'grains', 'rice'),
            ('pantry', 'grains', 'millets'),
            ('pantry', 'grains', 'wheat'),
            ('pantry', 'grains', 'oats'),
            ('pantry', 'grains', 'other'),
            ('pantry', 'pulses', 'lentils'),
            ('pantry', 'pulses', 'beans'),
            ('pantry', 'pulses', 'chickpeas'),
            ('pantry', 'pulses', 'other'),
            ('pantry', 'flours', 'wheat_flour'),
            ('pantry', 'flours', 'rice_flour'),
            ('pantry', 'flours', 'besan'),
            ('pantry', 'flours', 'other'),
            ('pantry', 'spices', 'whole'),
            ('pantry', 'spices', 'powdered'),
            ('pantry', 'spices', 'blends'),
            ('pantry', 'spices', 'other'),
            ('pantry', 'powders', 'baking'),
            ('pantry', 'powders', 'protein'),
            ('pantry', 'powders', 'other'),
            ('pantry', 'oils', 'cooking_oils'),
            ('pantry', 'oils', 'ghee'),
            ('pantry', 'oils', 'vinegar'),
            ('pantry', 'oils', 'other'),
            ('pantry', 'snacks', 'chips'),
            ('pantry', 'snacks', 'biscuits'),
            ('pantry', 'snacks', 'nuts'),
            ('pantry', 'snacks', 'other'),
            ('pantry', 'canned', 'vegetables'),
            ('pantry', 'canned', 'beans'),
            ('pantry', 'canned', 'fish'),
            ('pantry', 'canned', 'other'),
            ('pantry', 'baking', 'sugar'),
            ('pantry', 'baking', 'baking_powder'),
            ('pantry', 'baking', 'cocoa'),
            ('pantry', 'baking', 'other'),

            -- freezer
            ('freezer', 'frozen_vegetables', 'mixed'),
            ('freezer', 'frozen_vegetables', 'leafy'),
            ('freezer', 'frozen_vegetables', 'other'),
            ('freezer', 'frozen_fruits', 'berries'),
            ('freezer', 'frozen_fruits', 'other'),
            ('freezer', 'meat_seafood', 'meat'),
            ('freezer', 'meat_seafood', 'fish'),
            ('freezer', 'meat_seafood', 'other'),
            ('freezer', 'prepared_meals', 'leftovers'),
            ('freezer', 'prepared_meals', 'ready_to_cook'),
            ('freezer', 'prepared_meals', 'other'),
            ('freezer', 'desserts', 'ice_cream'),
            ('freezer', 'desserts', 'other'),

            -- counter
            ('counter', 'produce', 'fruits'),
            ('counter', 'produce', 'vegetables'),
            ('counter', 'produce', 'other'),
            ('counter', 'breads', 'bread'),
            ('counter', 'breads', 'buns'),
            ('counter', 'breads', 'other'),
            ('counter', 'snacks', 'chips'),
            ('counter', 'snacks', 'biscuits'),
            ('counter', 'snacks', 'nuts'),
            ('counter', 'snacks', 'other'),
            ('counter', 'other', 'other')
    ) AS v(storage_location, category, subcategory)
)
SELECT storage_location, category, subcategory
FROM allowed
ORDER BY storage_location, category, subcategory;
