-- Vector sync queue (event-driven only)
-- Date: 2026-01-10
-- Purpose:
--  - Provide an event-driven queue for embedding/vector updates
--  - Explicitly avoids cron/scheduled jobs; updates are triggered from event_log

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema='public' AND table_name='vector_sync_queue'
    ) THEN
        EXECUTE $sql$
            CREATE TABLE public.vector_sync_queue (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                queued_at TIMESTAMPTZ NOT NULL DEFAULT now(),

                user_id UUID NULL,
                event_type TEXT NOT NULL,
                event_ts TIMESTAMPTZ NULL,
                entity_type TEXT NULL,
                entity_id TEXT NULL,

                embedding_provider TEXT NOT NULL DEFAULT 'noop',
                embedding_version TEXT NOT NULL,

                payload JSONB NOT NULL DEFAULT '{}'::jsonb,

                status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'processing', 'done', 'failed')),
                attempts INT NOT NULL DEFAULT 0,
                processed_at TIMESTAMPTZ NULL,
                last_error TEXT NULL
            );
        $sql$;

        EXECUTE 'CREATE INDEX vector_sync_queue_status_idx ON public.vector_sync_queue(status, queued_at)';
        EXECUTE 'CREATE INDEX vector_sync_queue_user_ts_idx ON public.vector_sync_queue(user_id, queued_at DESC)';

        EXECUTE 'ALTER TABLE public.vector_sync_queue ENABLE ROW LEVEL SECURITY';

        DROP POLICY IF EXISTS vector_sync_queue_read_own ON public.vector_sync_queue;
        EXECUTE 'CREATE POLICY vector_sync_queue_read_own ON public.vector_sync_queue FOR SELECT USING (auth.uid() = user_id)';

        DROP POLICY IF EXISTS vector_sync_queue_insert_own ON public.vector_sync_queue;
        EXECUTE 'CREATE POLICY vector_sync_queue_insert_own ON public.vector_sync_queue FOR INSERT WITH CHECK (auth.uid() = user_id)';
    END IF;
END $$;
