-- ============================================================================
-- SESSION SECURITY & DEVICE TRACKING
-- ============================================================================
-- Purpose: Prevent credential sharing with 2-device limit enforcement
-- Features: Device fingerprinting, IP tracking, location detection, email alerts
-- Phase 1: Immediate - Hard security limits
-- Created: 2026-01-02

-- ============================================================================
-- SESSION TRACKING TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.user_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    
    -- Session identification
    session_token_hash TEXT NOT NULL, -- Hash of JWT access_token for identification
    supabase_session_id TEXT, -- Supabase's session ID if available
    
    -- Device fingerprinting
    device_type TEXT, -- 'mobile', 'tablet', 'desktop', 'web'
    device_os TEXT, -- 'iOS 17.2', 'Android 14', 'Windows 11', 'macOS 14'
    device_model TEXT, -- 'iPhone 15 Pro', 'Samsung Galaxy S24', 'Chrome Browser'
    browser TEXT, -- 'Safari 17', 'Chrome 120', 'Firefox 121'
    user_agent TEXT, -- Full user agent string
    device_fingerprint TEXT, -- Unique device identifier (composite)
    
    -- Network & Location
    ip_address INET, -- IPv4 or IPv6 address
    country_code TEXT, -- 'US', 'CA', 'GB', etc.
    country_name TEXT, -- 'United States', 'Canada', etc.
    region TEXT, -- 'California', 'Ontario', etc.
    city TEXT, -- 'San Francisco', 'Toronto', etc.
    latitude DECIMAL(10, 8), -- For distance calculations
    longitude DECIMAL(11, 8),
    timezone TEXT, -- 'America/Los_Angeles', 'America/Toronto'
    isp_name TEXT, -- Internet Service Provider
    
    -- Session lifecycle
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_active_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ, -- When JWT expires
    signed_out_at TIMESTAMPTZ, -- Manual sign out
    revoked_at TIMESTAMPTZ, -- Force revoked (suspicious activity)
    
    -- Security flags
    is_active BOOLEAN DEFAULT true,
    is_current BOOLEAN DEFAULT false, -- Mark current session
    is_trusted BOOLEAN DEFAULT false, -- Recognized device
    is_suspicious BOOLEAN DEFAULT false, -- Flagged by anomaly detection
    suspicious_reason TEXT, -- Why flagged
    
    -- Audit
    login_count INTEGER DEFAULT 1, -- How many times this device logged in
    first_seen_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT unique_active_session UNIQUE (user_id, session_token_hash)
);

-- Indexes for performance
CREATE INDEX idx_user_sessions_user_id ON public.user_sessions(user_id);
CREATE INDEX idx_user_sessions_active ON public.user_sessions(user_id, is_active) WHERE is_active = true;
CREATE INDEX idx_user_sessions_last_active ON public.user_sessions(last_active_at DESC);
CREATE INDEX idx_user_sessions_device_fp ON public.user_sessions(user_id, device_fingerprint);
CREATE INDEX idx_user_sessions_ip ON public.user_sessions(ip_address);

COMMENT ON TABLE public.user_sessions IS 'Track all user sessions for device limit enforcement and security monitoring';

-- ============================================================================
-- SECURITY EVENTS LOG
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.security_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    session_id UUID REFERENCES public.user_sessions(id) ON DELETE SET NULL,
    
    -- Event details
    event_type TEXT NOT NULL CHECK (event_type IN (
        'login_attempt',
        'login_success',
        'login_blocked', -- Device limit reached
        'login_suspicious', -- Location/behavior anomaly
        'device_limit_exceeded',
        'concurrent_location_detected', -- Multiple locations simultaneously
        'new_device_detected',
        'unrecognized_ip',
        'unusual_activity',
        'password_changed',
        'force_signout_all',
        'session_expired',
        'session_revoked'
    )),
    severity TEXT DEFAULT 'info' CHECK (severity IN ('info', 'warning', 'critical')),
    
    -- Context
    ip_address INET,
    device_info TEXT,
    location TEXT, -- City, Country
    user_agent TEXT,
    
    -- Details
    description TEXT,
    metadata JSONB, -- Additional context
    
    -- Resolution
    action_taken TEXT, -- 'blocked', 'allowed', 'email_sent', 'force_logout'
    requires_user_action BOOLEAN DEFAULT false,
    resolved_at TIMESTAMPTZ,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_security_events_user_id ON public.security_events(user_id);
CREATE INDEX idx_security_events_type ON public.security_events(event_type);
CREATE INDEX idx_security_events_severity ON public.security_events(severity);
CREATE INDEX idx_security_events_created ON public.security_events(created_at DESC);
CREATE INDEX idx_security_events_unresolved ON public.security_events(user_id, requires_user_action) 
    WHERE requires_user_action = true AND resolved_at IS NULL;

COMMENT ON TABLE public.security_events IS 'Audit log of all security-related events for monitoring and compliance';

-- ============================================================================
-- TRUSTED DEVICES
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.trusted_devices (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    
    -- Device identification
    device_fingerprint TEXT NOT NULL,
    device_name TEXT, -- User-friendly name: "John's iPhone", "Work Laptop"
    device_type TEXT,
    device_os TEXT,
    
    -- Trust establishment
    trusted_at TIMESTAMPTZ DEFAULT NOW(),
    last_used_at TIMESTAMPTZ DEFAULT NOW(),
    trust_expires_at TIMESTAMPTZ, -- Optional: expire trust after 90 days inactive
    
    -- Metadata
    is_active BOOLEAN DEFAULT true,
    notes TEXT,
    
    CONSTRAINT unique_trusted_device UNIQUE (user_id, device_fingerprint)
);

CREATE INDEX idx_trusted_devices_user_id ON public.trusted_devices(user_id);
CREATE INDEX idx_trusted_devices_fingerprint ON public.trusted_devices(device_fingerprint);

COMMENT ON TABLE public.trusted_devices IS 'User-approved devices that bypass some security checks';

-- ============================================================================
-- EMAIL NOTIFICATIONS QUEUE
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.security_notifications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    
    -- Notification details
    notification_type TEXT NOT NULL CHECK (notification_type IN (
        'new_device_login',
        'suspicious_login',
        'device_limit_reached',
        'concurrent_location',
        'password_changed',
        'unusual_activity'
    )),
    
    -- Recipient
    email TEXT NOT NULL,
    
    -- Content
    subject TEXT NOT NULL,
    body_text TEXT NOT NULL, -- Plain text version
    body_html TEXT, -- HTML version
    
    -- Context
    event_context JSONB, -- Device info, location, etc.
    
    -- Delivery
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'sent', 'failed', 'bounced')),
    sent_at TIMESTAMPTZ,
    failed_reason TEXT,
    retry_count INTEGER DEFAULT 0,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_security_notifications_user_id ON public.security_notifications(user_id);
CREATE INDEX idx_security_notifications_status ON public.security_notifications(status);
CREATE INDEX idx_security_notifications_pending ON public.security_notifications(created_at) 
    WHERE status = 'pending';

COMMENT ON TABLE public.security_notifications IS 'Queue for sending security alert emails to users';

-- ============================================================================
-- UPDATE USERS TABLE
-- ============================================================================

-- Add security-related columns to users table
ALTER TABLE public.users 
ADD COLUMN IF NOT EXISTS max_devices INTEGER DEFAULT 2,
ADD COLUMN IF NOT EXISTS current_active_devices INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS last_security_check_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS security_alerts_enabled BOOLEAN DEFAULT true,
ADD COLUMN IF NOT EXISTS suspicious_activity_score DECIMAL(5,2) DEFAULT 0.0;

COMMENT ON COLUMN public.users.max_devices IS 'Maximum concurrent device limit (default: 2 to prevent sharing)';
COMMENT ON COLUMN public.users.current_active_devices IS 'Current count of active sessions (updated on login/logout)';
COMMENT ON COLUMN public.users.suspicious_activity_score IS 'ML-based anomaly score (0-100, >70 = suspicious)';

-- ============================================================================
-- FUNCTIONS FOR SESSION MANAGEMENT
-- ============================================================================

-- Function to get active session count
CREATE OR REPLACE FUNCTION get_active_session_count(p_user_id UUID)
RETURNS INTEGER AS $$
BEGIN
    RETURN (
        SELECT COUNT(*)
        FROM public.user_sessions
        WHERE user_id = p_user_id 
            AND is_active = true
            AND (signed_out_at IS NULL AND revoked_at IS NULL)
            AND (expires_at IS NULL OR expires_at > NOW())
    );
END;
$$ LANGUAGE plpgsql;

-- Function to check if device limit exceeded
CREATE OR REPLACE FUNCTION check_device_limit(p_user_id UUID)
RETURNS BOOLEAN AS $$
DECLARE
    v_max_devices INTEGER;
    v_active_count INTEGER;
BEGIN
    -- Get user's max device limit
    SELECT max_devices INTO v_max_devices
    FROM public.users
    WHERE id = p_user_id;
    
    -- Get current active session count
    v_active_count := get_active_session_count(p_user_id);
    
    -- Return true if limit NOT exceeded (can log in)
    RETURN v_active_count < v_max_devices;
END;
$$ LANGUAGE plpgsql;

-- Function to revoke all other sessions (keep current)
CREATE OR REPLACE FUNCTION revoke_other_sessions(
    p_user_id UUID,
    p_current_session_hash TEXT
)
RETURNS INTEGER AS $$
DECLARE
    v_revoked_count INTEGER;
BEGIN
    WITH revoked AS (
        UPDATE public.user_sessions
        SET 
            is_active = false,
            revoked_at = NOW()
        WHERE user_id = p_user_id
            AND session_token_hash != p_current_session_hash
            AND is_active = true
        RETURNING id
    )
    SELECT COUNT(*) INTO v_revoked_count FROM revoked;
    
    -- Update active device count
    UPDATE public.users
    SET current_active_devices = get_active_session_count(p_user_id)
    WHERE id = p_user_id;
    
    RETURN v_revoked_count;
END;
$$ LANGUAGE plpgsql;

-- Function to calculate distance between two locations
CREATE OR REPLACE FUNCTION calculate_distance_miles(
    lat1 DECIMAL, lon1 DECIMAL,
    lat2 DECIMAL, lon2 DECIMAL
)
RETURNS DECIMAL AS $$
DECLARE
    radius_miles CONSTANT DECIMAL := 3958.8; -- Earth's radius in miles
    dlat DECIMAL;
    dlon DECIMAL;
    a DECIMAL;
    c DECIMAL;
BEGIN
    -- Haversine formula
    dlat := RADIANS(lat2 - lat1);
    dlon := RADIANS(lon2 - lon1);
    
    a := SIN(dlat/2) * SIN(dlat/2) + 
         COS(RADIANS(lat1)) * COS(RADIANS(lat2)) * 
         SIN(dlon/2) * SIN(dlon/2);
    
    c := 2 * ATAN2(SQRT(a), SQRT(1-a));
    
    RETURN radius_miles * c;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Function to detect concurrent sessions in different locations
CREATE OR REPLACE FUNCTION detect_concurrent_locations(
    p_user_id UUID,
    p_min_distance_miles DECIMAL DEFAULT 50
)
RETURNS TABLE (
    session1_id UUID,
    session2_id UUID,
    distance_miles DECIMAL,
    location1 TEXT,
    location2 TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        s1.id,
        s2.id,
        calculate_distance_miles(s1.latitude, s1.longitude, s2.latitude, s2.longitude),
        CONCAT(s1.city, ', ', s1.country_name),
        CONCAT(s2.city, ', ', s2.country_name)
    FROM public.user_sessions s1
    CROSS JOIN public.user_sessions s2
    WHERE s1.user_id = p_user_id
        AND s2.user_id = p_user_id
        AND s1.id < s2.id  -- Avoid duplicates
        AND s1.is_active = true
        AND s2.is_active = true
        AND s1.latitude IS NOT NULL
        AND s2.latitude IS NOT NULL
        AND ABS(EXTRACT(EPOCH FROM (s1.last_active_at - s2.last_active_at))) < 300  -- Within 5 minutes
        AND calculate_distance_miles(s1.latitude, s1.longitude, s2.latitude, s2.longitude) > p_min_distance_miles;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- TRIGGERS
-- ============================================================================

-- Auto-update last_active_at on session activity
CREATE OR REPLACE FUNCTION update_session_last_active()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_active_at := NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_session_last_active
    BEFORE UPDATE ON public.user_sessions
    FOR EACH ROW
    WHEN (OLD.last_active_at IS DISTINCT FROM NEW.last_active_at OR OLD.is_active IS DISTINCT FROM NEW.is_active)
    EXECUTE FUNCTION update_session_last_active();

-- Auto-update users.current_active_devices count
CREATE OR REPLACE FUNCTION update_active_device_count()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' OR TG_OP = 'UPDATE' THEN
        UPDATE public.users
        SET current_active_devices = get_active_session_count(NEW.user_id)
        WHERE id = NEW.user_id;
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE public.users
        SET current_active_devices = get_active_session_count(OLD.user_id)
        WHERE id = OLD.user_id;
        RETURN OLD;
    END IF;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_active_device_count
    AFTER INSERT OR UPDATE OR DELETE ON public.user_sessions
    FOR EACH ROW
    EXECUTE FUNCTION update_active_device_count();

-- ============================================================================
-- VIEWS FOR MONITORING
-- ============================================================================

-- Active sessions summary
CREATE OR REPLACE VIEW v_active_sessions AS
SELECT 
    us.user_id,
    u.email,
    COUNT(*) as active_session_count,
    u.max_devices,
    CASE 
        WHEN COUNT(*) > u.max_devices THEN true 
        ELSE false 
    END as exceeds_limit,
    ARRAY_AGG(
        JSONB_BUILD_OBJECT(
            'device', us.device_os,
            'location', CONCAT(us.city, ', ', us.country_name),
            'ip', us.ip_address,
            'last_active', us.last_active_at
        ) ORDER BY us.last_active_at DESC
    ) as sessions
FROM public.user_sessions us
JOIN public.users u ON us.user_id = u.id
WHERE us.is_active = true
    AND us.signed_out_at IS NULL
    AND us.revoked_at IS NULL
GROUP BY us.user_id, u.email, u.max_devices;

COMMENT ON VIEW v_active_sessions IS 'Real-time view of all active sessions with device limit violations';

-- Suspicious activity summary
CREATE OR REPLACE VIEW v_suspicious_activity AS
SELECT 
    se.user_id,
    u.email,
    COUNT(*) FILTER (WHERE se.created_at > NOW() - INTERVAL '24 hours') as events_24h,
    COUNT(*) FILTER (WHERE se.severity = 'critical') as critical_events,
    MAX(se.created_at) as last_event_at,
    ARRAY_AGG(DISTINCT se.event_type) as event_types
FROM public.security_events se
JOIN public.users u ON se.user_id = u.id
WHERE se.created_at > NOW() - INTERVAL '7 days'
    AND se.severity IN ('warning', 'critical')
GROUP BY se.user_id, u.email
HAVING COUNT(*) > 3
ORDER BY critical_events DESC, events_24h DESC;

COMMENT ON VIEW v_suspicious_activity IS 'Users with suspicious security events in the past week';

-- ============================================================================
-- GRANT PERMISSIONS
-- ============================================================================

-- Allow authenticated users to read their own sessions
ALTER TABLE public.user_sessions ENABLE ROW LEVEL SECURITY;

CREATE POLICY user_sessions_select_own ON public.user_sessions
    FOR SELECT
    USING (auth.uid() = user_id);

-- Allow authenticated users to read their own security events
ALTER TABLE public.security_events ENABLE ROW LEVEL SECURITY;

CREATE POLICY security_events_select_own ON public.security_events
    FOR SELECT
    USING (auth.uid() = user_id);

-- ============================================================================
-- INITIAL DATA
-- ============================================================================

-- Update existing users with default max_devices
UPDATE public.users
SET max_devices = 2
WHERE max_devices IS NULL;

-- ============================================================================
-- MIGRATION COMPLETE
-- ============================================================================
COMMENT ON SCHEMA public IS 'Phase 1 security migration complete: Device tracking, IP monitoring, session limits';
