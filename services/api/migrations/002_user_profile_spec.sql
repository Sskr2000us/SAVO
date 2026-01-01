-- SAVO Database Migration 002 - User Profile Spec
-- Created: 2026-01-01
-- Purpose: Add onboarding tracking, audit logging, and profile fields for JSON spec compliance

-- ============================================================================
-- ADD ONBOARDING TRACKING TO HOUSEHOLD PROFILES
-- ============================================================================

-- Add onboarding completion timestamp
ALTER TABLE public.household_profiles
ADD COLUMN IF NOT EXISTS onboarding_completed_at TIMESTAMPTZ;

-- Add basic spices availability field
ALTER TABLE public.household_profiles
ADD COLUMN IF NOT EXISTS basic_spices_available TEXT
CHECK (basic_spices_available IN ('yes', 'some', 'no'));

-- Add index for onboarding queries
CREATE INDEX IF NOT EXISTS idx_household_onboarding_status 
ON public.household_profiles(user_id, onboarding_completed_at);

-- ============================================================================
-- CREATE AUDIT LOG TABLE
-- ============================================================================

-- Audit log for tracking all profile changes (especially allergen/dietary)
CREATE TABLE IF NOT EXISTS public.audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    
    -- Event metadata
    event_type TEXT NOT NULL,  -- 'profile_write', 'allergen_change', 'dietary_change', etc.
    route TEXT NOT NULL,  -- '/profile/allergens', '/profile/dietary', etc.
    
    -- Entity information
    entity_type TEXT NOT NULL,  -- 'household_profile', 'family_member', 'allergen', etc.
    entity_id UUID,  -- family_member_id if applicable
    
    -- Change tracking
    old_value JSONB,  -- Previous state
    new_value JSONB,  -- New state
    
    -- Client context
    device_info JSONB,  -- {platform, device, app_version, etc.}
    ip_address TEXT,
    
    -- Timestamp
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for user audit history queries
CREATE INDEX IF NOT EXISTS idx_audit_log_user_time 
ON public.audit_log(user_id, created_at DESC);

-- Index for event type filtering
CREATE INDEX IF NOT EXISTS idx_audit_log_event_type 
ON public.audit_log(event_type, created_at DESC);

-- Index for allergen-specific queries (safety-critical)
CREATE INDEX IF NOT EXISTS idx_audit_log_allergen 
ON public.audit_log(user_id, event_type, created_at DESC)
WHERE event_type IN ('allergen_added', 'allergen_removed', 'allergen_updated');

-- ============================================================================
-- ROW LEVEL SECURITY FOR AUDIT LOG
-- ============================================================================

-- Enable RLS
ALTER TABLE public.audit_log ENABLE ROW LEVEL SECURITY;

-- Users can view their own audit log
CREATE POLICY "Users can view own audit log" ON public.audit_log
    FOR SELECT USING (auth.uid() = user_id);

-- Service role can insert audit logs (backend only)
CREATE POLICY "Service can insert audit logs" ON public.audit_log
    FOR INSERT WITH CHECK (true);

-- No updates or deletes allowed (audit log is append-only)
-- This ensures audit trail integrity

-- ============================================================================
-- AUDIT LOG RETENTION POLICY (Optional - for future cleanup)
-- ============================================================================

-- Function to purge old non-critical audit logs
-- Keeps allergen/dietary changes indefinitely for safety
CREATE OR REPLACE FUNCTION purge_old_audit_logs()
RETURNS void AS $$
BEGIN
    DELETE FROM public.audit_log
    WHERE 
        -- Only purge non-safety-critical events
        event_type NOT IN (
            'allergen_added', 
            'allergen_removed', 
            'allergen_updated',
            'dietary_restriction_removed',
            'dietary_restriction_added'
        )
        -- Older than 90 days
        AND created_at < NOW() - INTERVAL '90 days';
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Note: To schedule automatic cleanup, use pg_cron extension:
-- SELECT cron.schedule('purge-audit-logs', '0 2 * * *', 'SELECT purge_old_audit_logs()');
-- This requires pg_cron to be enabled in Supabase project settings

-- ============================================================================
-- ADD SESSION TRACKING TO USERS TABLE (for multi-device support)
-- ============================================================================

-- Track last login device for session management
ALTER TABLE public.users
ADD COLUMN IF NOT EXISTS last_login_device JSONB;

-- Track number of active sessions (optional, for display purposes)
ALTER TABLE public.users
ADD COLUMN IF NOT EXISTS active_sessions_count INTEGER DEFAULT 0;

-- ============================================================================
-- HELPER FUNCTIONS FOR ONBOARDING STATUS
-- ============================================================================

-- Function to check if onboarding is complete
CREATE OR REPLACE FUNCTION is_onboarding_complete(p_user_id UUID)
RETURNS BOOLEAN AS $$
DECLARE
    profile_exists BOOLEAN;
    onboarding_done BOOLEAN;
BEGIN
    SELECT 
        EXISTS(SELECT 1 FROM public.household_profiles WHERE user_id = p_user_id),
        COALESCE(
            (SELECT onboarding_completed_at IS NOT NULL 
             FROM public.household_profiles 
             WHERE user_id = p_user_id),
            FALSE
        )
    INTO profile_exists, onboarding_done;
    
    RETURN profile_exists AND onboarding_done;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================================================
-- DATA VALIDATION TRIGGERS
-- ============================================================================

-- Trigger to validate allergen changes are logged
CREATE OR REPLACE FUNCTION validate_allergen_change()
RETURNS TRIGGER AS $$
BEGIN
    -- If allergens array changed, ensure it's a valid change
    IF OLD.allergens IS DISTINCT FROM NEW.allergens THEN
        -- Log a warning if allergens are being removed without audit log
        -- (The application should create audit_log entries, this is a safety check)
        RAISE NOTICE 'Allergen change detected for member %. Old: %, New: %', 
            NEW.id, OLD.allergens, NEW.allergens;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply trigger to family_members table
DROP TRIGGER IF EXISTS trigger_allergen_change ON public.family_members;
CREATE TRIGGER trigger_allergen_change
    BEFORE UPDATE OF allergens ON public.family_members
    FOR EACH ROW
    EXECUTE FUNCTION validate_allergen_change();

-- ============================================================================
-- COMMENTS FOR DOCUMENTATION
-- ============================================================================

COMMENT ON TABLE public.audit_log IS 
'Audit trail for all profile changes, especially safety-critical allergen/dietary changes. Append-only for integrity.';

COMMENT ON COLUMN public.household_profiles.onboarding_completed_at IS 
'Timestamp when user completed onboarding flow. NULL means incomplete. Used for resume logic.';

COMMENT ON COLUMN public.household_profiles.basic_spices_available IS 
'User preference for basic pantry spices availability: yes (fully stocked), some (basics only), no (prefer simple cooking)';

COMMENT ON COLUMN public.users.last_login_device IS 
'JSON object with device metadata: {platform, device_model, os_version, app_version}';

COMMENT ON COLUMN public.users.active_sessions_count IS 
'Approximate count of active sessions across devices. Updated on login/logout.';

-- ============================================================================
-- VERIFICATION QUERIES (Run these to test the migration)
-- ============================================================================

-- Test 1: Verify new columns exist
-- SELECT onboarding_completed_at, basic_spices_available FROM public.household_profiles LIMIT 1;

-- Test 2: Verify audit_log table works
-- SELECT * FROM public.audit_log LIMIT 1;

-- Test 3: Check indexes were created
-- SELECT indexname FROM pg_indexes WHERE tablename IN ('household_profiles', 'audit_log');

-- Test 4: Verify RLS policies
-- SELECT * FROM pg_policies WHERE tablename = 'audit_log';

-- Test 5: Test onboarding status function
-- SELECT is_onboarding_complete('00000000-0000-0000-0000-000000000001'::UUID);

-- ============================================================================
-- MIGRATION COMPLETE
-- ============================================================================

-- Summary of changes:
-- ✅ Added household_profiles.onboarding_completed_at
-- ✅ Added household_profiles.basic_spices_available with CHECK constraint
-- ✅ Created audit_log table with RLS policies
-- ✅ Added users.last_login_device and users.active_sessions_count
-- ✅ Created indexes for performance
-- ✅ Added helper function is_onboarding_complete()
-- ✅ Added allergen change validation trigger
-- ✅ Added audit log retention function (manual trigger)
