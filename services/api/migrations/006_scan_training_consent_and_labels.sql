-- Migration: Scan training consent + retention + ground-truth labels
-- Adds opt-in + retention policy fields and a table to store confirmed labels for training.

BEGIN;

-- 1) Add consent fields to household_profiles (idempotent)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema='public' AND table_name='household_profiles' AND column_name='scan_training_opt_in'
    ) THEN
        ALTER TABLE public.household_profiles
            ADD COLUMN scan_training_opt_in BOOLEAN NOT NULL DEFAULT FALSE;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema='public' AND table_name='household_profiles' AND column_name='scan_training_opt_in_at'
    ) THEN
        ALTER TABLE public.household_profiles
            ADD COLUMN scan_training_opt_in_at TIMESTAMPTZ NULL;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema='public' AND table_name='household_profiles' AND column_name='scan_training_retention_days'
    ) THEN
        ALTER TABLE public.household_profiles
            ADD COLUMN scan_training_retention_days INTEGER NOT NULL DEFAULT 90;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'household_profiles_scan_training_retention_days_check'
    ) THEN
        ALTER TABLE public.household_profiles
            ADD CONSTRAINT household_profiles_scan_training_retention_days_check
            CHECK (scan_training_retention_days >= 0 AND scan_training_retention_days <= 3650);
    END IF;
END $$;

COMMENT ON COLUMN public.household_profiles.scan_training_opt_in IS
    'If true, user consents to using confirmed scan labels to improve recognition.';
COMMENT ON COLUMN public.household_profiles.scan_training_opt_in_at IS
    'Timestamp when user last opted in to scan training.';
COMMENT ON COLUMN public.household_profiles.scan_training_retention_days IS
    'Retention window in days for training samples captured after opt-in.';


-- 2) Create table to store ground-truth labels from confirmation (append-only)
CREATE TABLE IF NOT EXISTS public.scan_training_labels (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    scan_id UUID NOT NULL,
    detected_id UUID NULL,

    confirmed_name TEXT NOT NULL,
    original_detected_name TEXT NULL,
    bbox JSONB NULL,
    image_url TEXT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NULL
);

-- Foreign keys (best-effort; only add if not already present)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_schema='public'
          AND table_name='scan_training_labels'
          AND constraint_name='scan_training_labels_user_id_fkey'
    ) THEN
        ALTER TABLE public.scan_training_labels
            ADD CONSTRAINT scan_training_labels_user_id_fkey
            FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_schema='public'
          AND table_name='scan_training_labels'
          AND constraint_name='scan_training_labels_scan_id_fkey'
    ) THEN
        ALTER TABLE public.scan_training_labels
            ADD CONSTRAINT scan_training_labels_scan_id_fkey
            FOREIGN KEY (scan_id) REFERENCES public.ingredient_scans(id) ON DELETE CASCADE;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_schema='public'
          AND table_name='scan_training_labels'
          AND constraint_name='scan_training_labels_detected_id_fkey'
    ) THEN
        ALTER TABLE public.scan_training_labels
            ADD CONSTRAINT scan_training_labels_detected_id_fkey
            FOREIGN KEY (detected_id) REFERENCES public.detected_ingredients(id) ON DELETE SET NULL;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_scan_training_labels_user_created_at
    ON public.scan_training_labels(user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_scan_training_labels_expires_at
    ON public.scan_training_labels(expires_at);

COMMENT ON TABLE public.scan_training_labels IS
    'Ground-truth labels captured at confirmation time, gated by user opt-in and retention.';


-- 3) RLS (safe defaults)
ALTER TABLE public.scan_training_labels ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname='public' AND tablename='scan_training_labels' AND policyname='Users can view own training labels'
    ) THEN
        CREATE POLICY "Users can view own training labels" ON public.scan_training_labels
            FOR SELECT USING (auth.uid() = user_id);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname='public' AND tablename='scan_training_labels' AND policyname='Users can insert own training labels'
    ) THEN
        CREATE POLICY "Users can insert own training labels" ON public.scan_training_labels
            FOR INSERT WITH CHECK (auth.uid() = user_id);
    END IF;
END $$;

COMMIT;
