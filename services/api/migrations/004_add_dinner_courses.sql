-- Migration: Add dinner_courses to household_profiles
-- Date: 2026-01-02
-- Description: Add dinner_courses field to support multi-course meal planning

-- Add dinner_courses column to household_profiles (idempotent)
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='household_profiles' AND column_name='dinner_courses') THEN
        ALTER TABLE public.household_profiles ADD COLUMN dinner_courses INTEGER DEFAULT 2;
    END IF;
END $$;

-- Add constraint to ensure valid range (1-5 courses) - idempotent
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'check_dinner_courses_range') THEN
        ALTER TABLE public.household_profiles
        ADD CONSTRAINT check_dinner_courses_range 
        CHECK (dinner_courses BETWEEN 1 AND 5);
    END IF;
END $$;

-- Add comment for documentation
COMMENT ON COLUMN public.household_profiles.dinner_courses IS 
'Number of courses for dinner planning (1-5): 1=single dish, 2=main+side, 3=appetizer+main+dessert, etc.';

-- Verify the change
-- SELECT column_name, data_type, column_default 
-- FROM information_schema.columns 
-- WHERE table_name = 'household_profiles' AND column_name = 'dinner_courses';
