-- Central Media Asset Tracking + Append-only hardening
-- Date: 2026-01-09
-- Purpose:
--  - Track all stored media references centrally (expires_at, type, source, links)
--  - Support automated retention enforcement
--  - Keep historical logs append-only (defense-in-depth)

-- ============================================================================
-- 1) Central media_assets table
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.media_assets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Ownership (nullable for global/shared assets)
    user_id UUID NULL,

    -- Storage reference: "<bucket>/<path>" (never a signed URL)
    storage_ref TEXT NOT NULL,

    -- Classification
    media_type TEXT NOT NULL DEFAULT 'image', -- image
    asset_type TEXT NOT NULL,                 -- scan_reference|crop|training_crop|other
    source TEXT,                              -- scanning|video_scanning|inventory|system
    content_type TEXT,

    -- Retention
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NULL,

    -- Links to domain entities (all optional)
    scan_id UUID NULL,
    detected_id UUID NULL,
    observation_id UUID NULL,
    inventory_item_id UUID NULL,

    -- Metadata for audit/debug (dimensions, hashes, etc.)
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_media_assets_user_created ON public.media_assets(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_media_assets_expires_at ON public.media_assets(expires_at);
CREATE INDEX IF NOT EXISTS idx_media_assets_asset_type ON public.media_assets(asset_type);
CREATE INDEX IF NOT EXISTS idx_media_assets_scan_id ON public.media_assets(scan_id);

ALTER TABLE public.media_assets ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS media_assets_read_own ON public.media_assets;
CREATE POLICY media_assets_read_own ON public.media_assets
    FOR SELECT USING (auth.uid() = user_id);

DROP POLICY IF EXISTS media_assets_insert_own ON public.media_assets;
CREATE POLICY media_assets_insert_own ON public.media_assets
    FOR INSERT WITH CHECK (auth.uid() = user_id);

-- ============================================================================
-- 2) Append-only hardening triggers (event_log + scan_observations)
-- ============================================================================

-- event_log exists from 020; observations.scan_observations exists from 021.

DROP FUNCTION IF EXISTS public.prevent_update_delete();
CREATE OR REPLACE FUNCTION public.prevent_update_delete()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'This table is append-only; updates/deletes are not allowed';
END;
$$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema='public' AND table_name='event_log'
    ) THEN
        -- Prevent UPDATE/DELETE
        IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='event_log_prevent_update') THEN
            EXECUTE 'CREATE TRIGGER event_log_prevent_update BEFORE UPDATE ON public.event_log FOR EACH ROW EXECUTE FUNCTION public.prevent_update_delete()';
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='event_log_prevent_delete') THEN
            EXECUTE 'CREATE TRIGGER event_log_prevent_delete BEFORE DELETE ON public.event_log FOR EACH ROW EXECUTE FUNCTION public.prevent_update_delete()';
        END IF;
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema='observations' AND table_name='scan_observations'
    ) THEN
        IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='scan_observations_prevent_update') THEN
            EXECUTE 'CREATE TRIGGER scan_observations_prevent_update BEFORE UPDATE ON observations.scan_observations FOR EACH ROW EXECUTE FUNCTION public.prevent_update_delete()';
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='scan_observations_prevent_delete') THEN
            EXECUTE 'CREATE TRIGGER scan_observations_prevent_delete BEFORE DELETE ON observations.scan_observations FOR EACH ROW EXECUTE FUNCTION public.prevent_update_delete()';
        END IF;
    END IF;
END $$;
