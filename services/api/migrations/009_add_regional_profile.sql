-- Migration: Add regional_profile to household_profiles
-- Created: 2026-01-04
-- Purpose: Store fine-grained location + language context (e.g., Louisiana/Cajun) to guide strict cuisine enforcement.

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema='public'
          AND table_name='household_profiles'
          AND column_name='regional_profile'
    ) THEN
        ALTER TABLE public.household_profiles
            ADD COLUMN regional_profile JSONB NOT NULL DEFAULT '{}'::jsonb;
    END IF;
END $$;

COMMENT ON COLUMN public.household_profiles.regional_profile IS
    'Optional fine-grained location/language profile used to guide culturally authentic planning (e.g., state/city/languages/tags).';
