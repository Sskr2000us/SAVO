-- Learning: Observation -> Confirmation deltas (append-only feature store)
-- Date: 2026-01-09
-- Purpose:
--  - Capture structured correction signals (identity + quantity) without changing pantry truth
--  - Enable compounding improvements (container reuse, confidence decay features, etc.)

CREATE TABLE IF NOT EXISTS public.confirmation_deltas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    user_id UUID NOT NULL,
    scan_id UUID NULL,
    detected_id UUID NULL,

    action TEXT NOT NULL, -- confirmed|modified|rejected

    observed_name TEXT NULL,
    observed_canonical_name TEXT NULL,
    observed_ingredient_id UUID NULL,
    observed_confidence NUMERIC(3,2) NULL,
    observed_quantity NUMERIC(10,2) NULL,
    observed_unit TEXT NULL,

    confirmed_name TEXT NULL,
    confirmed_ingredient_id UUID NULL,
    confirmed_quantity NUMERIC(10,2) NULL,
    confirmed_unit TEXT NULL,

    quantity_was_correct BOOLEAN NULL,
    identity_was_correct BOOLEAN NULL,

    -- Container/packaging learning (non-PII)
    container_hash TEXT NULL,
    item_signature TEXT NULL,

    -- Versioning
    model_version TEXT NULL,
    release_version TEXT NULL,
    app_version TEXT NULL,
    taxonomy_version TEXT NULL,

    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_confirmation_deltas_user_created ON public.confirmation_deltas(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_confirmation_deltas_scan ON public.confirmation_deltas(scan_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_confirmation_deltas_detected ON public.confirmation_deltas(detected_id, created_at DESC);

ALTER TABLE public.confirmation_deltas ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS confirmation_deltas_read_own ON public.confirmation_deltas;
CREATE POLICY confirmation_deltas_read_own ON public.confirmation_deltas
    FOR SELECT USING (auth.uid() = user_id);

DROP POLICY IF EXISTS confirmation_deltas_insert_own ON public.confirmation_deltas;
CREATE POLICY confirmation_deltas_insert_own ON public.confirmation_deltas
    FOR INSERT WITH CHECK (auth.uid() = user_id);
