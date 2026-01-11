-- Video scan job queue for durable processing
-- Date: 2026-01-11
-- Purpose: Allow video scan processing to be resumed by a worker if the web process restarts.

BEGIN;

CREATE TABLE IF NOT EXISTS public.scan_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    scan_id UUID NOT NULL REFERENCES public.ingredient_scans(id) ON DELETE CASCADE,
    user_id UUID NOT NULL,

    job_type TEXT NOT NULL CHECK (job_type IN ('video_scan')),
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed')),

    -- Worker locking / takeover
    locked_at TIMESTAMPTZ NULL,
    locked_by TEXT NULL,

    -- Retry/diagnostics
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT scan_jobs_unique_scan_job UNIQUE (scan_id, job_type)
);

CREATE INDEX IF NOT EXISTS idx_scan_jobs_status_locked
    ON public.scan_jobs(status, locked_at);

CREATE INDEX IF NOT EXISTS idx_scan_jobs_user_created
    ON public.scan_jobs(user_id, created_at DESC);

COMMIT;
