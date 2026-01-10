-- Scan sessions for multi-frame pantry scanning (idempotent)
-- Date: 2026-01-09
-- Purpose:
--  - Track a user scan workflow across frame uploads/inference/confirmation
--  - Provide session status with frame counts + current stage

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_name = 'scan_sessions'
    ) THEN
        CREATE TABLE public.scan_sessions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            status TEXT NOT NULL DEFAULT 'active',
            stage TEXT NOT NULL DEFAULT 'collecting_frames',
            scan_type TEXT,
            location_hint TEXT,
            correlation_id TEXT,
            frames_received INTEGER NOT NULL DEFAULT 0,
            frames_usable INTEGER NOT NULL DEFAULT 0,
            last_quality_issues JSONB NOT NULL DEFAULT '[]'::jsonb,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb
        );

        CREATE INDEX scan_sessions_user_created_idx ON public.scan_sessions(user_id, created_at);
        CREATE INDEX scan_sessions_status_idx ON public.scan_sessions(status);
    END IF;
END $$;
