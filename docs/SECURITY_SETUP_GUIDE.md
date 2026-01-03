# Phase 1 Security - Setup Guide

## Step 1: Run Database Migration

1. Open Supabase SQL Editor
2. Copy the entire contents of `services/api/migrations/004_session_security_tracking.sql`
3. Execute the migration
4. Verify tables created:

```sql
-- Check tables
SELECT tablename FROM pg_tables 
WHERE schemaname = 'public' 
AND (tablename LIKE '%session%' OR tablename LIKE '%security%');

-- Should show:
-- user_sessions
-- security_events
-- trusted_devices
-- security_notifications

-- Check functions
SELECT proname FROM pg_proc 
WHERE proname LIKE '%session%' OR proname LIKE '%device%';

-- Should show:
-- get_active_session_count
-- check_device_limit
-- revoke_other_sessions
-- detect_concurrent_locations
-- calculate_distance_miles
```

## Step 2: Verify Backend Deployment

The backend automatically deploys to Render from GitHub. Verify:

```bash
# Check security endpoints are live
curl https://savo-ynp1.onrender.com/security/dashboard \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"

# Should return security dashboard data (or 401 if not authenticated)
```

## Step 3: Test Device Limit

### Test with Flutter App:

1. **Device 1**: Login from your phone
   - Should succeed ✅
   - Check logs: "✅ Session tracked: [location] - 1 devices"

2. **Device 2**: Login from web browser
   - Should succeed ✅
   - Check logs: "✅ Session tracked: [location] - 2 devices"

3. **Device 3**: Try login from another device
   - Should FAIL ❌ with error:
   - "Device limit reached. Maximum 2 devices allowed."
   - Login blocked, user signs out automatically

### Test Session Revocation:

1. On Device 1 or 2: Go to Settings → Device Security
2. Tap "Sign Out All Other Devices"
3. Should revoke 1 session
4. Now Device 3 can login (slot freed up)

## Step 4: Monitor Security Events

```sql
-- View all security events
SELECT * FROM security_events 
ORDER BY created_at DESC 
LIMIT 20;

-- View active sessions
SELECT * FROM v_active_sessions;

-- View users exceeding limits
SELECT * FROM v_active_sessions 
WHERE exceeds_limit = true;
```

## Step 5: Test Concurrent Location Detection

```sql
-- Manually create two distant sessions for testing
INSERT INTO user_sessions (
  user_id, 
  device_os, 
  city, 
  country_name, 
  latitude, 
  longitude, 
  is_active,
  last_active_at
) VALUES 
(
  'YOUR_USER_ID', 
  'iOS', 
  'San Francisco', 
  'United States', 
  37.7749, 
  -122.4194, 
  true,
  NOW()
),
(
  'YOUR_USER_ID', 
  'Android', 
  'New York', 
  'United States', 
  40.7128, 
  -74.0060, 
  true,
  NOW()
);

-- Run detection
SELECT * FROM detect_concurrent_locations('YOUR_USER_ID');

-- Should return:
-- distance_miles: ~2,900
-- location1: San Francisco, United States
-- location2: New York, United States

-- Check security events
SELECT * FROM security_events 
WHERE event_type = 'concurrent_location_detected'
AND user_id = 'YOUR_USER_ID';
```

## Troubleshooting

### Issue: Migration fails with "function already exists"
**Solution**: The migration is idempotent. Add `CREATE OR REPLACE` to functions or drop existing ones:
```sql
DROP FUNCTION IF EXISTS get_active_session_count CASCADE;
-- Then re-run migration
```

### Issue: Device limit not enforced
**Solution**: Check that login screen calls `trackLogin()`:
```dart
// Should be in login_screen.dart after Supabase auth
final securityService = SessionSecurityService(apiClient);
await securityService.trackLogin();
```

### Issue: IP geolocation returns empty
**Solution**: Free tier rate limited (45 requests/min). Wait 1 minute or upgrade API plan.

### Issue: Backend returns 500 error
**Solution**: Check Render logs for Python errors. Verify `httpx` package installed:
```bash
pip install httpx>=0.24.0
```

## Next Steps

After verifying Phase 1 works:

1. **Monitor**: Check security dashboard daily for violations
2. **Analyze**: Run queries to see how many users are attempting to share
3. **Optimize**: Adjust `max_devices` limit based on data
4. **Phase 2**: Implement IP diversity monitoring and 2FA
5. **Phase 3**: Add paid sharing program to monetize legitimate sharing

---

**Setup Complete!** ✅  
Device limits are now enforced. Credential sharing prevention is active.
