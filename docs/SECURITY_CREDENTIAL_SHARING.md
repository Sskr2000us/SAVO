# Security: Preventing Credential Sharing

## The Problem

**What if users share login credentials with friends?**
- Friend logs in from different location
- Uses household's meal plan inappropriately
- Violates terms of service (household use only)
- Security risk for actual household

## Prevention Strategies

### 1. ✅ Device/Session Management (Implemented)

**Active Sessions Screen:**
- Shows all logged-in devices with metadata:
  - Device type (iPhone, Android, Web)
  - Last login time and location (if available)
  - IP address
- **"Sign Out All Other Devices"** button
  - Keeps current session active
  - Revokes all other sessions
  - Forces re-login on those devices

**Use Case:**
- User sees unknown device logged in
- Clicks "Sign Out All Other Devices"
- Friend's access immediately revoked
- User changes password

### 2. ✅ Session Limits (Backend Enforcement)

**Supabase Configuration:**
```javascript
// In Supabase Dashboard → Auth Settings
Max concurrent sessions per user: 5
```

**Prevents:**
- Mass sharing (can't have 20 friends logged in)
- Limits abuse to reasonable household size

**Current Limit:** 5 devices (enough for family, not for friend group)

### 3. ⚠️ Geolocation Alerts (Future Enhancement)

**Detect Suspicious Logins:**
```python
# Backend logic
def check_login_location(user_id, new_ip):
    last_login = get_last_login_location(user_id)
    distance = calculate_distance(last_login.ip, new_ip)
    
    if distance > 500_miles:  # Different city/state
        send_alert_email(user_id, "New login from different location")
        require_2fa_verification()
```

**Alerts user:**
- "Login from New York - Is this you?"
- Option to deny access
- Automatically locks account if suspicious

### 4. ⚠️ Device Fingerprinting (Future)

**Track Known Devices:**
```dart
// Store device fingerprint on first login
String fingerprint = await getDeviceFingerprint();
// browser_name, os, screen_resolution, timezone, etc.

// On subsequent logins
if (!is_known_device(fingerprint)) {
    send_verification_email();
    require_2fa();
}
```

**Benefits:**
- Recognize household devices automatically
- Flag unknown devices
- Require extra verification

### 5. ✅ Terms of Service (Legal)

**Update Terms:**
- Account is for **single household use only**
- Sharing credentials outside household violates TOS
- Can result in account suspension
- Must be accepted during signup

**During Onboarding:**
```dart
Checkbox(
  label: "I confirm this account is for my household only",
  required: true,
)
```

### 6. ⚠️ Usage Pattern Detection (Future)

**Detect Anomalies:**
- Multiple simultaneous logins from different IPs
- Unusual meal plan generation (100 requests/hour)
- Pantry items added from multiple locations at once
- Different timezone activity patterns

**Action:**
- Flag account for review
- Require password change
- Contact user

### 7. ✅ Rate Limiting (Backend)

**Already Implemented:**
```python
# In FastAPI
@limiter.limit("100/hour")
async def generate_meal_plan():
    # Prevents abuse
```

**Prevents:**
- Friend group using account heavily
- API abuse
- Excessive resource consumption

### 8. ⚠️ Two-Factor Authentication (Future)

**Add 2FA Requirement:**
- SMS or authenticator app
- Required for sensitive actions
- Makes sharing harder (friend needs 2FA codes)

## Recommended Implementation Order

### Phase 1: Immediate (✅ Done)
1. ✅ Active Sessions screen with device list
2. ✅ "Sign Out All Other Devices" button
3. ✅ Session limit (5 devices via Supabase)
4. ✅ Terms of Service update

### Phase 2: Next Sprint (⚠️ Recommended)
1. Geolocation alerts for distant logins
2. Email notification on new device login
3. Device fingerprinting
4. "This is not me" button in alerts

### Phase 3: Future Enhancement
1. Two-factor authentication
2. Biometric login (face/fingerprint)
3. Usage pattern detection
4. Admin dashboard for support team
5. Account suspension workflow

## Current Security Features

### Already Implemented:
✅ **Password Requirements**
- Minimum 8 characters
- Must have uppercase, lowercase, number
- Supabase enforces these

✅ **Session Management**
- JWT tokens with expiration
- Automatic refresh
- Secure storage (flutter_secure_storage)

✅ **Rate Limiting**
- API endpoint limits
- Prevents brute force
- Prevents abuse

✅ **HTTPS Only**
- All traffic encrypted
- Supabase uses TLS 1.3

### Now Adding:
✅ **Active Sessions Management**
- View all logged-in devices
- Remote device logout
- Session metadata (device type, location)

## User Education

### During Onboarding:
Show message:
```
"SAVO is designed for household use.
Please don't share your login with people outside your home.

For security, you can:
- View active devices in Settings
- Sign out unknown devices remotely
- Change your password anytime"
```

### In Help Center:
**FAQ:**
- **Q:** Can I share my account with my neighbor?
  - **A:** No, accounts are for single household use only.

- **Q:** What if I see an unknown device?
  - **A:** Go to Settings → Sign Out All Other Devices, then change your password.

- **Q:** How many devices can I use?
  - **A:** Up to 5 devices per household (e.g., 2 phones, 2 tablets, 1 computer).

## Monitoring & Support

### For Support Team:
**Red Flags Dashboard:**
- Accounts with >5 concurrent sessions
- Logins from >2 countries
- Excessive API usage
- Multiple failed login attempts

**Actions:**
1. Email user: "We noticed unusual activity"
2. Temporary account lock
3. Require password reset
4. Review usage patterns

### Analytics:
Track:
- Average sessions per user
- Geographic distribution
- Device types
- Session duration

**Normal Pattern:**
- 2-3 devices
- Same city/region
- iOS + Web or Android + Web
- Regular daily usage

**Suspicious Pattern:**
- 10+ devices
- Multiple countries
- All login at similar times
- Bursty usage

## Balance: Security vs. Usability

### Don't Over-Restrict:
❌ Too strict = Bad UX
- Blocking legitimate family members
- Constant 2FA prompts
- Can't use at friend's house

✅ Good Balance:
- Allow 5 devices (reasonable for family)
- Alert on very distant logins (>500 miles)
- Easy device management
- 2FA optional but encouraged

## Implementation: Active Sessions

### Re-Add with Security Focus

**Purpose:** Security monitoring, NOT family member management

**Features:**
1. List all active sessions with:
   - Device type and name
   - Last active time
   - Approximate location (city-level)
   - "This is me" / "Not me" buttons

2. Actions:
   - "Sign Out This Device" (individual)
   - "Sign Out All Other Devices" (bulk)
   - "Report Suspicious" (flags for review)

3. Notifications:
   - Email on new device login
   - "Was this you?" confirmation link

**UI Message:**
```
"Manage Your Security
View devices accessing your household account.
If you see an unknown device, sign it out immediately."
```

## Recommendation

**Implement Phase 1 Now:**
1. ✅ Re-add Active Sessions (security focus)
2. ✅ Update messaging (not about family members)
3. ✅ Add "Sign Out All Other Devices"
4. ✅ Add to Terms of Service: household use only
5. ⚠️ Configure Supabase: max 5 sessions

**Phase 2 (Next Month):**
1. Email notifications on new device
2. Geolocation distance alerts
3. Device fingerprinting
4. Better session metadata

This balances security with household usability! 🔒
