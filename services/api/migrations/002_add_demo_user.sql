-- Add demo user for testing/development
-- This user exists in auth.users and can be referenced by the users table

-- Insert demo user into auth.users (if not exists)
INSERT INTO auth.users (
    id,
    instance_id,
    aud,
    role,
    email,
    encrypted_password,
    email_confirmed_at,
    created_at,
    updated_at,
    raw_app_meta_data,
    raw_user_meta_data,
    is_super_admin,
    confirmation_token,
    recovery_token,
    email_change_token_new,
    email_change
)
VALUES (
    '00000000-0000-0000-0000-000000000001'::uuid,
    '00000000-0000-0000-0000-000000000000'::uuid,
    'authenticated',
    'authenticated',
    'demo@savo.app',
    -- This is a bcrypt hash of 'demo_password_123' (change in production!)
    '$2a$10$rSBiVJvqSZFQ1KJzKGD5V.r3mJKI9h6qZmN3HJE8LKJ9K8F6zI7Ga',
    NOW(),
    NOW(),
    NOW(),
    '{"provider":"email","providers":["email"]}'::jsonb,
    '{"full_name":"Demo User"}'::jsonb,
    false,
    '',
    '',
    '',
    ''
)
ON CONFLICT (id) DO NOTHING;

-- Insert into public.users table
INSERT INTO public.users (
    id,
    email,
    full_name,
    created_at,
    updated_at,
    is_active,
    subscription_tier
)
VALUES (
    '00000000-0000-0000-0000-000000000001'::uuid,
    'demo@savo.app',
    'Demo User',
    NOW(),
    NOW(),
    true,
    'free'
)
ON CONFLICT (id) DO NOTHING;
