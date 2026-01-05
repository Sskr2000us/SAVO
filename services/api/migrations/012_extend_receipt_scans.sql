-- Extend receipt_scans for robustness + debugging (idempotent)
BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema='public' AND table_name='receipt_scans' AND column_name='raw_text'
    ) THEN
        ALTER TABLE public.receipt_scans
            ADD COLUMN raw_text TEXT;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema='public' AND table_name='receipt_scans' AND column_name='analysis_json'
    ) THEN
        ALTER TABLE public.receipt_scans
            ADD COLUMN analysis_json JSONB;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema='public' AND table_name='receipt_scans' AND column_name='status'
    ) THEN
        ALTER TABLE public.receipt_scans
            ADD COLUMN status TEXT NOT NULL DEFAULT 'parsed';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema='public' AND table_name='receipt_scans' AND column_name='confirmed_at'
    ) THEN
        ALTER TABLE public.receipt_scans
            ADD COLUMN confirmed_at TIMESTAMPTZ;
    END IF;
END $$;

DO $$
BEGIN
    -- Add/replace the status check constraint idempotently.
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'receipt_scans_status_check') THEN
        ALTER TABLE public.receipt_scans DROP CONSTRAINT receipt_scans_status_check;
    END IF;

    ALTER TABLE public.receipt_scans
        ADD CONSTRAINT receipt_scans_status_check
        CHECK (status IN ('parsed', 'confirmed', 'failed'));
END $$;

COMMIT;
