-- =====================================================
-- SAVO Decision Intelligence Schema
-- Migration: 007
-- Created: 2026-01-06
-- Purpose: Enable auto-action engine, confidence thresholds, and decision rules
-- Dependencies: Requires migration 005 (ingredient intelligence)
-- =====================================================

-- =====================================================
-- DECISION RULES ENGINE
-- =====================================================

-- Table: decision_rules
-- Purpose: Store decision rules for auto-action engine
CREATE TABLE decision_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_id TEXT UNIQUE NOT NULL,
    rule_name TEXT NOT NULL,
    rule_description TEXT,
    
    -- Rule conditions (JSONB for flexibility)
    -- Example: {"freshness_score_min": 0.80, "days_to_expiry_max": 1}
    conditions JSONB NOT NULL,
    
    -- Action and explanation
    action TEXT NOT NULL CHECK (action IN (
        'cook_now', 
        'store_better', 
        'substitute', 
        'buy', 
        'do_not_buy', 
        'discard',
        'monitor'
    )),
    explanation_template TEXT NOT NULL,
    
    -- Confidence thresholds
    confidence_min NUMERIC(3,2) DEFAULT 0.85 CHECK (confidence_min >= 0 AND confidence_min <= 1),
    auto_apply BOOLEAN DEFAULT false,
    
    -- Learning and performance
    times_applied INTEGER DEFAULT 0,
    times_accepted INTEGER DEFAULT 0,
    times_rejected INTEGER DEFAULT 0,
    acceptance_rate NUMERIC(3,2) GENERATED ALWAYS AS (
        CASE 
            WHEN times_applied > 0 THEN 
                ROUND(times_accepted::NUMERIC / times_applied::NUMERIC, 2)
            ELSE NULL
        END
    ) STORED,
    
    -- Priority and status
    priority INTEGER DEFAULT 100,
    is_active BOOLEAN DEFAULT true,
    
    -- Metadata
    created_by UUID REFERENCES auth.users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_decision_rules_action ON decision_rules(action);
CREATE INDEX idx_decision_rules_active ON decision_rules(is_active, priority DESC);
CREATE INDEX idx_decision_rules_rule_id ON decision_rules(rule_id);

COMMENT ON TABLE decision_rules IS 'Decision rules for auto-action engine';
COMMENT ON COLUMN decision_rules.conditions IS 'JSONB conditions like {"freshness_score_min": 0.80, "days_to_expiry_max": 1}';
COMMENT ON COLUMN decision_rules.confidence_min IS 'Minimum confidence (0.0-1.0) required to apply this rule';
COMMENT ON COLUMN decision_rules.auto_apply IS 'Whether to auto-apply this action when confidence meets threshold';

-- =====================================================
-- INGREDIENT ACTIONS & DECISIONS
-- =====================================================

-- Table: ingredient_actions
-- Purpose: Log all decisions made and user responses
CREATE TABLE ingredient_actions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    
    -- Ingredient context
    ingredient_id UUID REFERENCES master_ingredients(id),
    inventory_item_id UUID, -- Link to user_inventory if applicable
    
    -- Decision context
    decision_rule_id UUID REFERENCES decision_rules(id),
    recommended_action TEXT NOT NULL CHECK (recommended_action IN (
        'cook_now', 
        'store_better', 
        'substitute', 
        'buy', 
        'do_not_buy', 
        'discard',
        'monitor'
    )),
    confidence NUMERIC(3,2) NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    reason TEXT NOT NULL,
    
    -- Decision details
    decision_context JSONB, -- Store ingredient data at decision time
    was_auto_applied BOOLEAN DEFAULT false,
    
    -- User feedback
    user_response TEXT CHECK (user_response IN (
        'accepted', 
        'rejected', 
        'ignored', 
        'modified',
        NULL
    )),
    user_final_action TEXT CHECK (user_final_action IN (
        'cook_now', 
        'store_better', 
        'substitute', 
        'buy', 
        'do_not_buy', 
        'discard',
        'monitor',
        NULL
    )),
    feedback_notes TEXT,
    
    -- Timing
    recommended_at TIMESTAMPTZ DEFAULT NOW(),
    responded_at TIMESTAMPTZ,
    response_time_seconds INTEGER GENERATED ALWAYS AS (
        EXTRACT(EPOCH FROM (responded_at - recommended_at))::INTEGER
    ) STORED,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_actions_user ON ingredient_actions(user_id);
CREATE INDEX idx_actions_ingredient ON ingredient_actions(ingredient_id);
CREATE INDEX idx_actions_rule ON ingredient_actions(decision_rule_id);
CREATE INDEX idx_actions_response ON ingredient_actions(user_response);
CREATE INDEX idx_actions_recommended_at ON ingredient_actions(recommended_at DESC);
CREATE INDEX idx_actions_auto_applied ON ingredient_actions(was_auto_applied);

COMMENT ON TABLE ingredient_actions IS 'All decisions made by the system and user responses';
COMMENT ON COLUMN ingredient_actions.decision_context IS 'Snapshot of ingredient data at decision time for learning';
COMMENT ON COLUMN ingredient_actions.was_auto_applied IS 'Whether action was automatically applied (confidence >= threshold)';

-- =====================================================
-- DAILY HABIT LOOP
-- =====================================================

-- Table: daily_digests
-- Purpose: Store daily digest content and engagement
CREATE TABLE daily_digests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    
    -- Digest metadata
    digest_type TEXT NOT NULL CHECK (digest_type IN ('morning', 'evening', 'custom')),
    digest_date DATE NOT NULL,
    
    -- Content (JSONB for flexibility)
    content JSONB NOT NULL,
    
    -- Personalization
    expiring_ingredients UUID[], -- Array of ingredient IDs
    recommended_recipes UUID[], -- Array of recipe IDs
    waste_summary JSONB,
    streak_data JSONB,
    
    -- Delivery
    delivery_channel TEXT DEFAULT 'in_app' CHECK (delivery_channel IN ('in_app', 'push_notification', 'email')),
    was_sent BOOLEAN DEFAULT false,
    sent_at TIMESTAMPTZ,
    
    -- Engagement
    was_opened BOOLEAN DEFAULT false,
    opened_at TIMESTAMPTZ,
    was_actioned BOOLEAN DEFAULT false,
    actioned_at TIMESTAMPTZ,
    
    -- Metrics
    time_to_open_seconds INTEGER GENERATED ALWAYS AS (
        CASE 
            WHEN opened_at IS NOT NULL THEN 
                EXTRACT(EPOCH FROM (opened_at - sent_at))::INTEGER
            ELSE NULL
        END
    ) STORED,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_digests_user ON daily_digests(user_id);
CREATE INDEX idx_digests_type_date ON daily_digests(digest_type, digest_date DESC);
CREATE INDEX idx_digests_sent ON daily_digests(was_sent, sent_at DESC);
CREATE INDEX idx_digests_engagement ON daily_digests(was_opened, was_actioned);
CREATE UNIQUE INDEX idx_digests_user_type_date ON daily_digests(user_id, digest_type, digest_date);

COMMENT ON TABLE daily_digests IS 'Daily habit loop digests and engagement tracking';
COMMENT ON COLUMN daily_digests.content IS 'Personalized digest content in JSONB format';

-- Table: user_streaks
-- Purpose: Track user streaks (no waste, daily scan, etc.)
CREATE TABLE user_streaks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    
    -- Streak definition
    streak_type TEXT NOT NULL CHECK (streak_type IN (
        'no_waste',      -- Days without discarding ingredients
        'daily_scan',    -- Consecutive days with at least 1 scan
        'daily_cook',    -- Consecutive days with at least 1 recipe cooked
        'weekly_active'  -- Consecutive weeks with activity
    )),
    
    -- Current streak
    current_count INTEGER DEFAULT 0 CHECK (current_count >= 0),
    started_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Record streak
    longest_count INTEGER DEFAULT 0 CHECK (longest_count >= 0),
    longest_started_at TIMESTAMPTZ,
    longest_ended_at TIMESTAMPTZ,
    
    -- Status
    is_active BOOLEAN DEFAULT true,
    last_activity_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Reset conditions
    reset_reason TEXT,
    reset_at TIMESTAMPTZ,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_streaks_user ON user_streaks(user_id);
CREATE INDEX idx_streaks_type ON user_streaks(streak_type);
CREATE INDEX idx_streaks_active ON user_streaks(is_active, current_count DESC);
CREATE UNIQUE INDEX idx_streaks_user_type ON user_streaks(user_id, streak_type) WHERE is_active = true;

COMMENT ON TABLE user_streaks IS 'User habit streaks for gamification and retention';
COMMENT ON COLUMN user_streaks.streak_type IS 'Type of streak: no_waste, daily_scan, daily_cook, weekly_active';

-- Table: passive_learning_signals
-- Purpose: Track user behavior passively for learning
CREATE TABLE passive_learning_signals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    
    -- Signal metadata
    signal_type TEXT NOT NULL CHECK (signal_type IN (
        'digest_opened',       -- User opened daily digest
        'digest_closed',       -- User closed without action
        'item_clicked',        -- User clicked on ingredient/recipe
        'item_ignored',        -- User saw but didn't click
        'recipe_cooked',       -- User marked recipe as cooked
        'action_accepted',     -- User accepted recommendation
        'action_rejected',     -- User rejected recommendation
        'scan_performed',      -- User scanned ingredient
        'substitution_used'    -- User used substitution
    )),
    
    -- Entity context
    entity_type TEXT CHECK (entity_type IN ('ingredient', 'recipe', 'action', 'digest', 'substitution', NULL)),
    entity_id UUID,
    
    -- Additional context
    context JSONB,
    session_id TEXT,
    device_type TEXT,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_signals_user ON passive_learning_signals(user_id);
CREATE INDEX idx_signals_type ON passive_learning_signals(signal_type);
CREATE INDEX idx_signals_entity ON passive_learning_signals(entity_type, entity_id);
CREATE INDEX idx_signals_created_at ON passive_learning_signals(created_at DESC);

COMMENT ON TABLE passive_learning_signals IS 'Passive tracking of user behavior for learning and personalization';
COMMENT ON COLUMN passive_learning_signals.signal_type IS 'Type of user action tracked passively';

-- =====================================================
-- SELF-LEARNING LOOP
-- =====================================================

-- Table: model_performance_metrics
-- Purpose: Track model performance over time
CREATE TABLE model_performance_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Model identification
    model_type TEXT NOT NULL CHECK (model_type IN (
        'cv_identification',     -- Visual ingredient identification
        'substitution_ranking',  -- Substitution recommendations
        'decision_rules',        -- Decision rule accuracy
        'expiry_prediction',     -- Spoilage prediction
        'recipe_matching'        -- Recipe recommendation
    )),
    model_version TEXT,
    
    -- Metric details
    metric_name TEXT NOT NULL CHECK (metric_name IN (
        'accuracy',              -- Overall accuracy
        'precision',             -- Precision (true positives / predicted positives)
        'recall',                -- Recall (true positives / actual positives)
        'f1_score',              -- F1 score (harmonic mean of precision and recall)
        'acceptance_rate',       -- User acceptance rate
        'confidence_mean',       -- Average confidence score
        'confidence_median',     -- Median confidence score
        'human_confirmation_rate' -- % requiring human confirmation
    )),
    metric_value NUMERIC(5,4) NOT NULL CHECK (metric_value >= 0 AND metric_value <= 1),
    
    -- Context
    calculated_for_date DATE NOT NULL,
    sample_size INTEGER NOT NULL CHECK (sample_size > 0),
    calculation_method TEXT,
    
    -- Comparison
    previous_value NUMERIC(5,4),
    change_from_previous NUMERIC(5,4) GENERATED ALWAYS AS (
        metric_value - COALESCE(previous_value, metric_value)
    ) STORED,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_metrics_model_type ON model_performance_metrics(model_type, metric_name);
CREATE INDEX idx_metrics_date ON model_performance_metrics(calculated_for_date DESC);
CREATE INDEX idx_metrics_version ON model_performance_metrics(model_type, model_version);

COMMENT ON TABLE model_performance_metrics IS 'Model performance tracking for self-learning loop';
COMMENT ON COLUMN model_performance_metrics.metric_value IS 'Normalized metric value (0.0-1.0)';

-- Table: learning_feedback
-- Purpose: Track all feedback for learning updates
CREATE TABLE learning_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    
    -- Feedback type
    feedback_type TEXT NOT NULL CHECK (feedback_type IN (
        'cv_confirmation',       -- User confirmed ingredient ID
        'cv_correction',         -- User corrected ingredient ID
        'substitution_accept',   -- User accepted substitution
        'substitution_reject',   -- User rejected substitution
        'decision_accept',       -- User accepted decision
        'decision_reject'        -- User rejected decision
    )),
    
    -- Source entity
    source_entity_type TEXT NOT NULL CHECK (source_entity_type IN (
        'visual_scan_result',
        'ingredient_substitution',
        'ingredient_action'
    )),
    source_entity_id UUID NOT NULL,
    
    -- Feedback details
    was_correct BOOLEAN NOT NULL,
    confidence_at_decision NUMERIC(3,2),
    correction_data JSONB, -- Details about correction
    
    -- Learning impact
    processed BOOLEAN DEFAULT false,
    processed_at TIMESTAMPTZ,
    applied_updates JSONB, -- Log what was updated
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_feedback_user ON learning_feedback(user_id);
CREATE INDEX idx_feedback_type ON learning_feedback(feedback_type);
CREATE INDEX idx_feedback_source ON learning_feedback(source_entity_type, source_entity_id);
CREATE INDEX idx_feedback_processed ON learning_feedback(processed, created_at);

COMMENT ON TABLE learning_feedback IS 'User feedback for self-learning intelligence loop';
COMMENT ON COLUMN learning_feedback.correction_data IS 'Details about what was corrected for learning';

-- =====================================================
-- SUCCESS METRICS
-- =====================================================

-- Table: success_metrics_daily
-- Purpose: Daily aggregation of success metrics
CREATE TABLE success_metrics_daily (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    metric_date DATE NOT NULL,
    
    -- Scan-to-Action Rate
    total_scans INTEGER DEFAULT 0,
    scans_with_action INTEGER DEFAULT 0,
    scan_to_action_rate NUMERIC(5,4) GENERATED ALWAYS AS (
        CASE 
            WHEN total_scans > 0 THEN 
                ROUND(scans_with_action::NUMERIC / total_scans::NUMERIC, 4)
            ELSE NULL
        END
    ) STORED,
    
    -- Food Waste Reduction
    total_items_at_risk INTEGER DEFAULT 0,
    items_saved INTEGER DEFAULT 0,
    items_wasted INTEGER DEFAULT 0,
    waste_reduction_rate NUMERIC(5,4) GENERATED ALWAYS AS (
        CASE 
            WHEN total_items_at_risk > 0 THEN 
                ROUND(items_saved::NUMERIC / total_items_at_risk::NUMERIC, 4)
            ELSE NULL
        END
    ) STORED,
    
    -- User Engagement
    daily_active_users INTEGER DEFAULT 0,
    digests_sent INTEGER DEFAULT 0,
    digests_opened INTEGER DEFAULT 0,
    digest_open_rate NUMERIC(5,4) GENERATED ALWAYS AS (
        CASE 
            WHEN digests_sent > 0 THEN 
                ROUND(digests_opened::NUMERIC / digests_sent::NUMERIC, 4)
            ELSE NULL
        END
    ) STORED,
    
    -- Learning Performance
    avg_confidence NUMERIC(5,4),
    human_confirmation_rate NUMERIC(5,4),
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX idx_metrics_daily_date ON success_metrics_daily(metric_date);
CREATE INDEX idx_metrics_daily_created ON success_metrics_daily(created_at DESC);

COMMENT ON TABLE success_metrics_daily IS 'Daily aggregated success metrics';

-- =====================================================
-- HELPER FUNCTIONS
-- =====================================================

-- Function: Update decision rule statistics
CREATE OR REPLACE FUNCTION update_decision_rule_stats(
    p_rule_id UUID,
    p_was_accepted BOOLEAN
) RETURNS VOID AS $$
BEGIN
    UPDATE decision_rules
    SET 
        times_applied = times_applied + 1,
        times_accepted = times_accepted + CASE WHEN p_was_accepted THEN 1 ELSE 0 END,
        times_rejected = times_rejected + CASE WHEN NOT p_was_accepted THEN 1 ELSE 0 END,
        updated_at = NOW()
    WHERE id = p_rule_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION update_decision_rule_stats IS 'Update decision rule statistics based on user feedback';

-- Function: Update user streak
CREATE OR REPLACE FUNCTION update_user_streak(
    p_user_id UUID,
    p_streak_type TEXT,
    p_activity_occurred BOOLEAN
) RETURNS VOID AS $$
DECLARE
    v_streak RECORD;
BEGIN
    -- Get current streak
    SELECT * INTO v_streak
    FROM user_streaks
    WHERE user_id = p_user_id
    AND streak_type = p_streak_type
    AND is_active = true;
    
    IF v_streak IS NULL THEN
        -- Create new streak
        INSERT INTO user_streaks (user_id, streak_type, current_count, last_activity_at)
        VALUES (p_user_id, p_streak_type, CASE WHEN p_activity_occurred THEN 1 ELSE 0 END, NOW());
    ELSE
        IF p_activity_occurred THEN
            -- Increment streak
            UPDATE user_streaks
            SET 
                current_count = current_count + 1,
                last_activity_at = NOW(),
                longest_count = GREATEST(longest_count, current_count + 1),
                updated_at = NOW()
            WHERE id = v_streak.id;
        ELSE
            -- Reset streak
            UPDATE user_streaks
            SET 
                current_count = 0,
                is_active = false,
                reset_reason = 'activity_missed',
                reset_at = NOW(),
                updated_at = NOW()
            WHERE id = v_streak.id;
            
            -- Start new streak
            INSERT INTO user_streaks (user_id, streak_type, current_count, last_activity_at)
            VALUES (p_user_id, p_streak_type, 0, NOW());
        END IF;
    END IF;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION update_user_streak IS 'Update user streak based on activity';

-- Function: Calculate scan-to-action rate
CREATE OR REPLACE FUNCTION calculate_scan_to_action_rate(
    p_user_id UUID DEFAULT NULL,
    p_days_lookback INTEGER DEFAULT 30
) RETURNS NUMERIC AS $$
DECLARE
    v_rate NUMERIC;
BEGIN
    SELECT 
        CASE 
            WHEN COUNT(DISTINCT s.id) > 0 THEN
                ROUND(
                    COUNT(DISTINCT a.id)::NUMERIC / 
                    COUNT(DISTINCT s.id)::NUMERIC, 
                    4
                )
            ELSE 0
        END INTO v_rate
    FROM visual_scan_results s
    LEFT JOIN ingredient_actions a 
        ON s.user_confirmed_ingredient_id = a.ingredient_id
        AND a.created_at BETWEEN s.created_at AND s.created_at + INTERVAL '1 hour'
    WHERE 
        (p_user_id IS NULL OR s.user_id = p_user_id)
        AND s.created_at >= NOW() - (p_days_lookback || ' days')::INTERVAL;
    
    RETURN v_rate;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION calculate_scan_to_action_rate IS 'Calculate percentage of scans resulting in action';

-- =====================================================
-- RLS POLICIES
-- =====================================================

-- Enable RLS on all tables
ALTER TABLE decision_rules ENABLE ROW LEVEL SECURITY;
ALTER TABLE ingredient_actions ENABLE ROW LEVEL SECURITY;
ALTER TABLE daily_digests ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_streaks ENABLE ROW LEVEL SECURITY;
ALTER TABLE passive_learning_signals ENABLE ROW LEVEL SECURITY;
ALTER TABLE model_performance_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE learning_feedback ENABLE ROW LEVEL SECURITY;
ALTER TABLE success_metrics_daily ENABLE ROW LEVEL SECURITY;

-- Decision rules: Readable by all, writable by admin only
CREATE POLICY "Decision rules readable by authenticated users"
ON decision_rules FOR SELECT
TO authenticated
USING (true);

CREATE POLICY "Decision rules writable by admin"
ON decision_rules FOR ALL
TO authenticated
USING (auth.uid() IN (SELECT id FROM admin_users))
WITH CHECK (auth.uid() IN (SELECT id FROM admin_users));

-- Ingredient actions: User can only access their own
CREATE POLICY "Users can read their own ingredient actions"
ON ingredient_actions FOR SELECT
TO authenticated
USING (user_id = auth.uid());

CREATE POLICY "Users can create their own ingredient actions"
ON ingredient_actions FOR INSERT
TO authenticated
WITH CHECK (user_id = auth.uid());

CREATE POLICY "Users can update their own ingredient actions"
ON ingredient_actions FOR UPDATE
TO authenticated
USING (user_id = auth.uid())
WITH CHECK (user_id = auth.uid());

-- Daily digests: User can only access their own
CREATE POLICY "Users can read their own digests"
ON daily_digests FOR SELECT
TO authenticated
USING (user_id = auth.uid());

CREATE POLICY "Users can update their own digest engagement"
ON daily_digests FOR UPDATE
TO authenticated
USING (user_id = auth.uid())
WITH CHECK (user_id = auth.uid());

-- User streaks: User can only access their own
CREATE POLICY "Users can read their own streaks"
ON user_streaks FOR SELECT
TO authenticated
USING (user_id = auth.uid());

-- Passive signals: User can only access their own
CREATE POLICY "Users can read their own signals"
ON passive_learning_signals FOR SELECT
TO authenticated
USING (user_id = auth.uid());

CREATE POLICY "Users can create their own signals"
ON passive_learning_signals FOR INSERT
TO authenticated
WITH CHECK (user_id = auth.uid());

-- Model metrics: Readable by all authenticated
CREATE POLICY "Model metrics readable by authenticated users"
ON model_performance_metrics FOR SELECT
TO authenticated
USING (true);

-- Learning feedback: User can only access their own
CREATE POLICY "Users can read their own feedback"
ON learning_feedback FOR SELECT
TO authenticated
USING (user_id = auth.uid());

CREATE POLICY "Users can create their own feedback"
ON learning_feedback FOR INSERT
TO authenticated
WITH CHECK (user_id = auth.uid());

-- Success metrics: Readable by all authenticated
CREATE POLICY "Success metrics readable by authenticated users"
ON success_metrics_daily FOR SELECT
TO authenticated
USING (true);

-- =====================================================
-- SEED DATA: Decision Rules
-- =====================================================

-- Rule 1: Cook Now (High Freshness, Near Expiry)
INSERT INTO decision_rules (rule_id, rule_name, rule_description, conditions, action, explanation_template, confidence_min, auto_apply, priority)
VALUES (
    'DI_COOK_NOW_001',
    'Cook Immediately - Peak Freshness',
    'Recommend cooking when ingredient is at peak freshness but near expiry',
    '{"freshness_score_min": 0.80, "days_to_expiry_max": 1, "recognition_confidence_min": 0.85}',
    'cook_now',
    'This ingredient is at peak freshness and should be used today to avoid waste.',
    0.85,
    true,
    10
);

-- Rule 2: Store Better
INSERT INTO decision_rules (rule_id, rule_name, rule_description, conditions, action, explanation_template, confidence_min, auto_apply, priority)
VALUES (
    'DI_STORE_001',
    'Improve Storage Conditions',
    'Suggest better storage when conditions are suboptimal',
    '{"freshness_score_min": 0.60, "days_to_expiry_min": 2, "storage_quality_max": 0.70}',
    'store_better',
    'Storing this properly can extend its usability by 3-5 days. Check temperature and humidity.',
    0.70,
    false,
    20
);

-- Rule 3: Smart Substitute
INSERT INTO decision_rules (rule_id, rule_name, rule_description, conditions, action, explanation_template, confidence_min, auto_apply, priority)
VALUES (
    'DI_SUBSTITUTE_001',
    'Smart Substitution Available',
    'Recommend substitution when ingredient is missing but alternative exists',
    '{"ingredient_missing": true, "substitution_confidence_min": 0.70, "substitution_available": true}',
    'substitute',
    'A suitable substitute is available with minimal taste impact. Try this alternative.',
    0.85,
    true,
    15
);

-- Rule 4: Discard (Safety Concern)
INSERT INTO decision_rules (rule_id, rule_name, rule_description, conditions, action, explanation_template, confidence_min, auto_apply, priority)
VALUES (
    'DI_DISCARD_001',
    'Safety Concern - Discard',
    'Recommend discarding when safety risk is detected',
    '{"freshness_score_max": 0.30, "spoilage_detected": true}',
    'discard',
    '⚠️ Safety concern detected. This ingredient shows signs of spoilage and should be discarded.',
    0.90,
    false,
    5
);

-- Rule 5: Monitor (Good Condition)
INSERT INTO decision_rules (rule_id, rule_name, rule_description, conditions, action, explanation_template, confidence_min, auto_apply, priority)
VALUES (
    'DI_MONITOR_001',
    'Monitor - Good Condition',
    'No immediate action needed, ingredient is in good condition',
    '{"freshness_score_min": 0.70, "days_to_expiry_min": 5}',
    'monitor',
    'This ingredient is in good condition. No immediate action needed.',
    0.60,
    true,
    100
);

-- =====================================================
-- VERIFICATION
-- =====================================================

-- Verify table creation
DO $$
DECLARE
    table_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO table_count
    FROM information_schema.tables
    WHERE table_schema = 'public'
    AND table_name IN (
        'decision_rules',
        'ingredient_actions',
        'daily_digests',
        'user_streaks',
        'passive_learning_signals',
        'model_performance_metrics',
        'learning_feedback',
        'success_metrics_daily'
    );
    
    RAISE NOTICE 'Tables created: % / 8', table_count;
    
    IF table_count < 8 THEN
        RAISE EXCEPTION 'Migration incomplete: Expected 8 tables, found %', table_count;
    END IF;
END $$;

-- Verify seed data
DO $$
DECLARE
    rule_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO rule_count FROM decision_rules;
    RAISE NOTICE 'Decision rules seeded: %', rule_count;
    
    IF rule_count < 5 THEN
        RAISE WARNING 'Expected at least 5 seed rules, found %', rule_count;
    END IF;
END $$;

RAISE NOTICE 'Migration 007 completed successfully!';
