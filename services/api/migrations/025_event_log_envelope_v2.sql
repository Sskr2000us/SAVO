-- Event Envelope v2 (entity + schema/taxonomy version)
-- Date: 2026-01-09
-- Purpose:
--  - Extend event_log with entity_id/entity_type/schema_version/taxonomy_version
--  - Keep backward compatibility (existing columns remain)

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema='public' AND table_name='event_log'
    ) THEN
        ALTER TABLE public.event_log ADD COLUMN IF NOT EXISTS entity_id UUID;
        ALTER TABLE public.event_log ADD COLUMN IF NOT EXISTS entity_type TEXT;
        ALTER TABLE public.event_log ADD COLUMN IF NOT EXISTS schema_version INTEGER NOT NULL DEFAULT 1;
        ALTER TABLE public.event_log ADD COLUMN IF NOT EXISTS taxonomy_version TEXT;

        CREATE INDEX IF NOT EXISTS event_log_entity_ts_idx ON public.event_log(entity_id, event_ts DESC);
        CREATE INDEX IF NOT EXISTS event_log_type_entity_ts_idx ON public.event_log(event_type, entity_id, event_ts DESC);
    END IF;
END $$;
