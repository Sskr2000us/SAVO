-- Migration: Add session tracking to users table
-- Purpose: Track device information and session count for multi-device management
-- Date: 2026-01-01
-- Phase: H - Multi-device session sync

-- Add session tracking columns to public.users
ALTER TABLE public.users
ADD COLUMN IF NOT EXISTS last_login_device TEXT,
ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS active_sessions_count INTEGER DEFAULT 0;

-- Add index for performance on session queries
CREATE INDEX IF NOT EXISTS idx_users_last_login_at ON public.users(last_login_at DESC);

-- Add comment for documentation
COMMENT ON COLUMN public.users.last_login_device IS 'Device info from last login (e.g., "Android Device", "iOS Device", "Web Browser")';
COMMENT ON COLUMN public.users.last_login_at IS 'Timestamp of last successful login';
COMMENT ON COLUMN public.users.active_sessions_count IS 'Approximate count of active sessions across devices (informational only)';

-- Note: This is optional tracking for enhanced visibility
-- Supabase Auth manages actual session state via JWT tokens
-- These fields are for display/audit purposes only
