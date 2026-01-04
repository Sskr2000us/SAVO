-- Vision Scanning Database Schema
-- Date: 2026-01-02
-- Purpose: Support pantry/fridge scanning with vision AI

-- ============================================================================
-- 1. ingredient_scans: Store raw scan metadata
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.ingredient_scans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    
    -- Image data
    image_url TEXT,  -- S3/Supabase storage URL
    image_hash TEXT,  -- For deduplication
    image_metadata JSONB,  -- {width, height, format, size_bytes}
    
    -- Scan context
    scan_type TEXT NOT NULL CHECK (scan_type IN ('pantry', 'fridge', 'counter', 'shopping', 'other')),
    location_hint TEXT,  -- "kitchen", "pantry shelf 2", etc.
    
    -- Status tracking
    status TEXT NOT NULL DEFAULT 'processing' CHECK (status IN ('processing', 'completed', 'failed', 'cancelled')),
    processing_time_ms INTEGER,
    
    -- Vision API metadata
    vision_provider TEXT CHECK (vision_provider IN ('openai', 'google', 'hybrid')),
    api_cost_cents INTEGER,  -- Track API costs
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    
    CONSTRAINT valid_completed_at CHECK (
        (status = 'completed' AND completed_at IS NOT NULL) OR 
        (status != 'completed')
    )
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_ingredient_scans_user_created ON public.ingredient_scans(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ingredient_scans_status ON public.ingredient_scans(status) WHERE status = 'processing';
CREATE INDEX IF NOT EXISTS idx_ingredient_scans_image_hash ON public.ingredient_scans(image_hash) WHERE image_hash IS NOT NULL;

-- RLS policies
ALTER TABLE public.ingredient_scans ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname='public' AND tablename='ingredient_scans' AND policyname='Users can view their own scans'
    ) THEN
        EXECUTE $sql$
            CREATE POLICY "Users can view their own scans"
                ON public.ingredient_scans FOR SELECT
                USING (auth.uid() = user_id)
        $sql$;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname='public' AND tablename='ingredient_scans' AND policyname='Users can insert their own scans'
    ) THEN
        EXECUTE $sql$
            CREATE POLICY "Users can insert their own scans"
                ON public.ingredient_scans FOR INSERT
                WITH CHECK (auth.uid() = user_id)
        $sql$;
    END IF;
END $$;

-- ============================================================================
-- 2. detected_ingredients: Individual ingredients from each scan
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.detected_ingredients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scan_id UUID NOT NULL REFERENCES public.ingredient_scans(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    
    -- Detection data
    detected_name TEXT NOT NULL,  -- Raw name from Vision API
    canonical_name TEXT,  -- Normalized name (e.g., "whole milk" → "milk")
    confidence DECIMAL(3,2) NOT NULL CHECK (confidence BETWEEN 0.00 AND 1.00),
    
    -- Bounding box (if available)
    bbox JSONB,  -- {x, y, width, height, x_center, y_center}
    
    -- Close alternatives (for medium confidence)
    close_alternatives JSONB,  -- [{name, likelihood, reason}, ...]
    visual_similarity_group TEXT,  -- "leafy_greens", "root_vegetables", etc.
    
    -- User confirmation status
    confirmation_status TEXT NOT NULL DEFAULT 'pending' 
        CHECK (confirmation_status IN ('pending', 'confirmed', 'rejected', 'modified', 'skipped')),
    confirmed_name TEXT,  -- User's final choice
    confirmed_at TIMESTAMPTZ,
    
    -- Safety flags
    allergen_warnings JSONB,  -- [{allergen, severity, message}]
    dietary_warnings JSONB,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    CONSTRAINT valid_confirmation CHECK (
        (confirmation_status IN ('confirmed', 'modified') AND confirmed_name IS NOT NULL) OR
        (confirmation_status NOT IN ('confirmed', 'modified'))
    )
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_detected_ingredients_scan ON public.detected_ingredients(scan_id);
CREATE INDEX IF NOT EXISTS idx_detected_ingredients_user ON public.detected_ingredients(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_detected_ingredients_pending ON public.detected_ingredients(user_id, confirmation_status) 
    WHERE confirmation_status = 'pending';
CREATE INDEX IF NOT EXISTS idx_detected_ingredients_canonical ON public.detected_ingredients(canonical_name) 
    WHERE canonical_name IS NOT NULL;

-- RLS policies
ALTER TABLE public.detected_ingredients ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname='public' AND tablename='detected_ingredients' AND policyname='Users can view their detected ingredients'
    ) THEN
        EXECUTE $sql$
            CREATE POLICY "Users can view their detected ingredients"
                ON public.detected_ingredients FOR SELECT
                USING (auth.uid() = user_id)
        $sql$;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname='public' AND tablename='detected_ingredients' AND policyname='Users can insert detected ingredients'
    ) THEN
        EXECUTE $sql$
            CREATE POLICY "Users can insert detected ingredients"
                ON public.detected_ingredients FOR INSERT
                WITH CHECK (auth.uid() = user_id)
        $sql$;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname='public' AND tablename='detected_ingredients' AND policyname='Users can update their detected ingredients'
    ) THEN
        EXECUTE $sql$
            CREATE POLICY "Users can update their detected ingredients"
                ON public.detected_ingredients FOR UPDATE
                USING (auth.uid() = user_id)
        $sql$;
    END IF;
END $$;

-- ============================================================================
-- 3. user_pantry: Current confirmed pantry inventory
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.user_pantry (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    
    -- Ingredient data
    ingredient_name TEXT NOT NULL,  -- Canonical name
    display_name TEXT NOT NULL,  -- User-friendly name
    category TEXT,  -- "protein", "vegetable", "spice", etc.
    
    -- Quantity tracking (optional)
    quantity DECIMAL(10,2),
    unit TEXT,  -- "pieces", "lbs", "cups", etc.
    
    -- Expiry tracking (optional)
    expires_at TIMESTAMPTZ,
    expiry_reminder_sent BOOLEAN DEFAULT FALSE,
    
    -- Source tracking
    source TEXT NOT NULL CHECK (source IN ('scan', 'manual', 'recipe', 'shopping')),
    source_scan_id UUID REFERENCES public.ingredient_scans(id) ON DELETE SET NULL,
    source_detected_id UUID REFERENCES public.detected_ingredients(id) ON DELETE SET NULL,
    
    -- Status
    status TEXT NOT NULL DEFAULT 'available' 
        CHECK (status IN ('available', 'low', 'used', 'expired', 'removed')),
    
    -- Timestamps
    added_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_used_at TIMESTAMPTZ,
    removed_at TIMESTAMPTZ,
    
    -- Metadata
    notes TEXT,
    tags TEXT[],  -- ["organic", "bulk_buy", "freezer"]
    
    CONSTRAINT unique_user_ingredient UNIQUE(user_id, ingredient_name),
    CONSTRAINT valid_removed CHECK (
        (status = 'removed' AND removed_at IS NOT NULL) OR
        (status != 'removed')
    )
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_user_pantry_user_status ON public.user_pantry(user_id, status) 
    WHERE status = 'available';
CREATE INDEX IF NOT EXISTS idx_user_pantry_expires ON public.user_pantry(user_id, expires_at) 
    WHERE expires_at IS NOT NULL AND status = 'available';
CREATE INDEX IF NOT EXISTS idx_user_pantry_category ON public.user_pantry(user_id, category) 
    WHERE status = 'available';

-- RLS policies
ALTER TABLE public.user_pantry ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname='public' AND tablename='user_pantry' AND policyname='Users can manage their pantry'
    ) THEN
        EXECUTE $sql$
            CREATE POLICY "Users can manage their pantry"
                ON public.user_pantry FOR ALL
                USING (auth.uid() = user_id)
        $sql$;
    END IF;
END $$;

-- ============================================================================
-- 4. scan_feedback: User corrections and feedback
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.scan_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    scan_id UUID NOT NULL REFERENCES public.ingredient_scans(id) ON DELETE CASCADE,
    detected_id UUID REFERENCES public.detected_ingredients(id) ON DELETE SET NULL,
    
    -- Feedback type
    feedback_type TEXT NOT NULL 
        CHECK (feedback_type IN ('correction', 'missing', 'false_positive', 'rating', 'comment')),
    
    -- Correction data
    detected_name TEXT,  -- What AI detected
    correct_name TEXT,  -- What it should have been
    
    -- Rating data (1-5 stars)
    overall_rating INTEGER CHECK (overall_rating BETWEEN 1 AND 5),
    accuracy_rating INTEGER CHECK (accuracy_rating BETWEEN 1 AND 5),
    speed_rating INTEGER CHECK (speed_rating BETWEEN 1 AND 5),
    
    -- Comments
    comment TEXT,
    
    -- Context
    was_confident BOOLEAN,  -- Was AI confident when it was wrong?
    had_alternatives BOOLEAN,  -- Did close alternatives include correct answer?
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    CONSTRAINT valid_correction CHECK (
        (feedback_type = 'correction' AND detected_name IS NOT NULL AND correct_name IS NOT NULL) OR
        (feedback_type != 'correction')
    ),
    CONSTRAINT valid_rating CHECK (
        (feedback_type = 'rating' AND overall_rating IS NOT NULL) OR
        (feedback_type != 'rating')
    )
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_scan_feedback_user ON public.scan_feedback(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_scan_feedback_scan ON public.scan_feedback(scan_id);
CREATE INDEX IF NOT EXISTS idx_scan_feedback_type ON public.scan_feedback(feedback_type);

-- RLS policies
ALTER TABLE public.scan_feedback ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname='public' AND tablename='scan_feedback' AND policyname='Users can manage their feedback'
    ) THEN
        EXECUTE $sql$
            CREATE POLICY "Users can manage their feedback"
                ON public.scan_feedback FOR ALL
                USING (auth.uid() = user_id)
        $sql$;
    END IF;
END $$;

-- ============================================================================
-- 5. scan_corrections: Track detection errors for model improvement
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.scan_corrections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Correction data
    detected_name TEXT NOT NULL,
    correct_name TEXT NOT NULL,
    confidence DECIMAL(3,2) NOT NULL,
    
    -- Context
    scan_id UUID REFERENCES public.ingredient_scans(id) ON DELETE SET NULL,
    user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    vision_provider TEXT,
    
    -- Error analysis
    error_type TEXT CHECK (error_type IN (
        'misidentification',  -- Detected wrong item
        'missed',  -- Didn't detect visible item
        'false_positive',  -- Detected non-existent item
        'name_variant',  -- Right item, wrong name ("cilantro" vs "coriander")
        'quality_issue'  -- Image quality problem
    )),
    
    -- Aggregation tracking
    occurrence_count INTEGER DEFAULT 1,
    last_occurrence TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Status
    reviewed BOOLEAN DEFAULT FALSE,
    fixed_in_version TEXT,  -- Track when correction is incorporated
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    CONSTRAINT unique_correction UNIQUE(detected_name, correct_name)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_scan_corrections_reviewed ON public.scan_corrections(reviewed) WHERE NOT reviewed;
CREATE INDEX IF NOT EXISTS idx_scan_corrections_count ON public.scan_corrections(occurrence_count DESC);
CREATE INDEX IF NOT EXISTS idx_scan_corrections_detected ON public.scan_corrections(detected_name);

-- RLS: No RLS on corrections - backend-only table
-- Admin/analytics can access for model improvement

-- ============================================================================
-- 6. Materialized view: Scanning metrics
-- ============================================================================
CREATE MATERIALIZED VIEW IF NOT EXISTS public.scanning_metrics AS
SELECT 
    DATE(s.created_at) as scan_date,
    COUNT(DISTINCT s.id) as total_scans,
    COUNT(DISTINCT s.user_id) as active_users,
    
    -- Detection metrics
    COUNT(d.id) as total_detections,
    AVG(d.confidence) as avg_confidence,
    
    -- Confirmation metrics
    COUNT(*) FILTER (WHERE d.confirmation_status = 'confirmed') as confirmed_count,
    COUNT(*) FILTER (WHERE d.confirmation_status = 'modified') as modified_count,
    COUNT(*) FILTER (WHERE d.confirmation_status = 'rejected') as rejected_count,
    
    -- Success rate
    (COUNT(*) FILTER (WHERE d.confirmation_status = 'confirmed')::FLOAT / 
     NULLIF(COUNT(d.id), 0) * 100) as confirmation_rate_pct,
    
    -- Performance
    AVG(s.processing_time_ms) as avg_processing_ms,
    SUM(s.api_cost_cents) as total_cost_cents
FROM public.ingredient_scans s
LEFT JOIN public.detected_ingredients d ON d.scan_id = s.id
WHERE s.status = 'completed'
GROUP BY DATE(s.created_at);

-- Refresh schedule (run daily via cron job)
CREATE UNIQUE INDEX IF NOT EXISTS idx_scanning_metrics_date ON public.scanning_metrics(scan_date);

-- ============================================================================
-- 7. Helper functions
-- ============================================================================

-- Function: Get user's current pantry inventory
CREATE OR REPLACE FUNCTION public.get_user_pantry(p_user_id UUID)
RETURNS TABLE (
    ingredient_name TEXT,
    display_name TEXT,
    category TEXT,
    quantity DECIMAL,
    unit TEXT,
    expires_at TIMESTAMPTZ,
    days_until_expiry INTEGER,
    added_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        up.ingredient_name,
        up.display_name,
        up.category,
        up.quantity,
        up.unit,
        up.expires_at,
        CASE 
            WHEN up.expires_at IS NOT NULL 
            THEN EXTRACT(DAYS FROM (up.expires_at - NOW()))::INTEGER
            ELSE NULL
        END as days_until_expiry,
        up.added_at
    FROM public.user_pantry up
    WHERE up.user_id = p_user_id
      AND up.status = 'available'
    ORDER BY up.added_at DESC;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function: Get scanning accuracy for user
CREATE OR REPLACE FUNCTION public.get_user_scanning_accuracy(p_user_id UUID)
RETURNS TABLE (
    total_detections BIGINT,
    confirmed_count BIGINT,
    modified_count BIGINT,
    rejected_count BIGINT,
    accuracy_pct DECIMAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COUNT(*)::BIGINT as total_detections,
        COUNT(*) FILTER (WHERE confirmation_status = 'confirmed')::BIGINT as confirmed_count,
        COUNT(*) FILTER (WHERE confirmation_status = 'modified')::BIGINT as modified_count,
        COUNT(*) FILTER (WHERE confirmation_status = 'rejected')::BIGINT as rejected_count,
        (COUNT(*) FILTER (WHERE confirmation_status = 'confirmed')::DECIMAL / 
         NULLIF(COUNT(*), 0) * 100) as accuracy_pct
    FROM public.detected_ingredients
    WHERE user_id = p_user_id
      AND confirmation_status IN ('confirmed', 'modified', 'rejected');
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================================================
-- 8. Triggers for automatic updates
-- ============================================================================

-- Trigger: Auto-update scan status when all ingredients confirmed
CREATE OR REPLACE FUNCTION public.check_scan_completion()
RETURNS TRIGGER AS $$
BEGIN
    -- If this ingredient was just confirmed/rejected
    IF NEW.confirmation_status IN ('confirmed', 'rejected', 'modified', 'skipped') THEN
        -- Check if all ingredients for this scan are now resolved
        IF NOT EXISTS (
            SELECT 1 FROM public.detected_ingredients
            WHERE scan_id = NEW.scan_id
              AND confirmation_status = 'pending'
        ) THEN
            -- All resolved - update scan status
            UPDATE public.ingredient_scans
            SET status = 'completed',
                completed_at = NOW()
            WHERE id = NEW.scan_id
              AND status != 'completed';
        END IF;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trigger_check_scan_completion') THEN
        EXECUTE $sql$
            CREATE TRIGGER trigger_check_scan_completion
                AFTER UPDATE ON public.detected_ingredients
                FOR EACH ROW
                WHEN (OLD.confirmation_status IS DISTINCT FROM NEW.confirmation_status)
                EXECUTE FUNCTION public.check_scan_completion()
        $sql$;
    END IF;
END $$;

-- Trigger: Auto-add to pantry when ingredient confirmed
CREATE OR REPLACE FUNCTION public.auto_add_to_pantry()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.confirmation_status = 'confirmed' AND NEW.confirmed_name IS NOT NULL THEN
        INSERT INTO public.user_pantry (
            user_id,
            ingredient_name,
            display_name,
            source,
            source_scan_id,
            source_detected_id,
            status
        ) VALUES (
            NEW.user_id,
            LOWER(NEW.confirmed_name),
            NEW.confirmed_name,
            'scan',
            NEW.scan_id,
            NEW.id,
            'available'
        )
        ON CONFLICT (user_id, ingredient_name) 
        DO UPDATE SET
            status = 'available',
            added_at = NOW(),
            removed_at = NULL;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trigger_auto_add_to_pantry') THEN
        EXECUTE $sql$
            CREATE TRIGGER trigger_auto_add_to_pantry
                AFTER UPDATE ON public.detected_ingredients
                FOR EACH ROW
                WHEN (OLD.confirmation_status IS DISTINCT FROM NEW.confirmation_status)
                EXECUTE FUNCTION public.auto_add_to_pantry()
        $sql$;
    END IF;
END $$;

-- Trigger: Track correction occurrence
CREATE OR REPLACE FUNCTION public.track_correction()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.feedback_type = 'correction' THEN
        INSERT INTO public.scan_corrections (
            detected_name,
            correct_name,
            confidence,
            scan_id,
            user_id,
            error_type
        ) VALUES (
            NEW.detected_name,
            NEW.correct_name,
            (SELECT confidence FROM public.detected_ingredients WHERE id = NEW.detected_id),
            NEW.scan_id,
            NEW.user_id,
            'misidentification'
        )
        ON CONFLICT (detected_name, correct_name)
        DO UPDATE SET
            occurrence_count = public.scan_corrections.occurrence_count + 1,
            last_occurrence = NOW();
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trigger_track_correction') THEN
        EXECUTE $sql$
            CREATE TRIGGER trigger_track_correction
                AFTER INSERT ON public.scan_feedback
                FOR EACH ROW
                EXECUTE FUNCTION public.track_correction()
        $sql$;
    END IF;
END $$;

-- ============================================================================
-- Migration complete
-- ============================================================================

-- Grant permissions (adjust based on your setup)
GRANT SELECT, INSERT, UPDATE ON public.ingredient_scans TO authenticated;
GRANT SELECT, INSERT, UPDATE ON public.detected_ingredients TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.user_pantry TO authenticated;
GRANT SELECT, INSERT ON public.scan_feedback TO authenticated;
GRANT SELECT ON public.scanning_metrics TO authenticated;
GRANT EXECUTE ON FUNCTION public.get_user_pantry TO authenticated;
GRANT EXECUTE ON FUNCTION public.get_user_scanning_accuracy TO authenticated;

-- Comments for documentation
COMMENT ON TABLE public.ingredient_scans IS 'Stores metadata for each pantry/fridge scanning session';
COMMENT ON TABLE public.detected_ingredients IS 'Individual ingredients detected by Vision API with confidence scores';
COMMENT ON TABLE public.user_pantry IS 'Current confirmed pantry inventory for each user';
COMMENT ON TABLE public.scan_feedback IS 'User corrections and ratings for improving detection accuracy';
COMMENT ON TABLE public.scan_corrections IS 'Aggregated corrections for model training and improvement';
COMMENT ON MATERIALIZED VIEW public.scanning_metrics IS 'Daily aggregated metrics for monitoring scanning performance';
