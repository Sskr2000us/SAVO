-- Canonical event envelope + event log
-- Date: 2026-01-09
-- Purpose:
--  - Provide a consistent, queryable event stream across services
--  - Support analytics/ML monitoring without storing raw frames

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_name = 'event_log'
    ) THEN
        CREATE TABLE public.event_log (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            event_type TEXT NOT NULL,
            event_ts TIMESTAMPTZ NOT NULL DEFAULT now(),

            user_id UUID,
            household_id UUID,
            session_id UUID,

            model_version TEXT,
            release_version TEXT,
            app_version TEXT,

            payload JSONB NOT NULL DEFAULT '{}'::jsonb
        );

        CREATE INDEX event_log_event_ts_idx ON public.event_log(event_ts DESC);
        CREATE INDEX event_log_event_type_ts_idx ON public.event_log(event_type, event_ts DESC);
        CREATE INDEX event_log_user_ts_idx ON public.event_log(user_id, event_ts DESC);
        CREATE INDEX event_log_session_ts_idx ON public.event_log(session_id, event_ts DESC);

        ALTER TABLE public.event_log ENABLE ROW LEVEL SECURITY;

        -- Users can read their own events.
        IF NOT EXISTS (
            SELECT 1 FROM pg_policies
            WHERE schemaname='public' AND tablename='event_log' AND policyname='Users can view their own events'
        ) THEN
            EXECUTE $sql$
                CREATE POLICY "Users can view their own events"
                    ON public.event_log FOR SELECT
                    USING (auth.uid() = user_id)
            $sql$;
        END IF;

        -- Users can insert events attributed to themselves (server-side writes should use service key).
        IF NOT EXISTS (
            SELECT 1 FROM pg_policies
            WHERE schemaname='public' AND tablename='event_log' AND policyname='Users can insert their own events'
        ) THEN
            EXECUTE $sql$
                CREATE POLICY "Users can insert their own events"
                    ON public.event_log FOR INSERT
                    WITH CHECK (auth.uid() = user_id)
            $sql$;
        END IF;
    END IF;
END $$;
