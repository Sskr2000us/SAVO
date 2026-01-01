# Supabase Setup Guide for SAVO

## Prerequisites
- Supabase account (free tier works)
- Project created in Supabase Dashboard

---

## Step 1: Create Supabase Project

1. Go to [https://supabase.com](https://supabase.com)
2. Sign in or create account
3. Click "New Project"
4. Fill in:
   - **Name:** SAVO
   - **Database Password:** (generate strong password - save it!)
   - **Region:** Choose closest to your users
   - **Pricing Plan:** Free
5. Click "Create new project"
6. Wait ~2 minutes for provisioning

---

## Step 2: Run Database Migrations

### Migration 1: Initial Schema

1. Go to **SQL Editor** in Supabase Dashboard
2. Click **New Query**
3. Copy contents of [services/api/migrations/001_initial_schema.sql](services/api/migrations/001_initial_schema.sql)
4. Paste and click **Run**
5. Verify tables created: `users`, `household_profiles`, `family_members`, `inventory`, `meal_plans`, `recipe_history`

### Migration 2: User Profile Spec

1. Still in **SQL Editor**, click **New Query**
2. Copy contents of [services/api/migrations/002_user_profile_spec.sql](services/api/migrations/002_user_profile_spec.sql)
3. Paste and click **Run**
4. Verify:
   - `household_profiles` has new columns: `onboarding_completed_at`, `basic_spices_available`
   - `users` has new column: `last_login_device`
   - `audit_log` table created
   - Trigger `validate_allergen_change` exists

---

## Step 3: Get API Credentials

1. Go to **Settings** → **API** in Supabase Dashboard
2. Copy these values:

```
Project URL: https://xxxxx.supabase.co
anon public key: eyJhbGc...
service_role key: eyJhbGc... (keep secret!)
JWT Secret: your-jwt-secret (keep secret!)
```

---

## Step 4: Configure Backend (FastAPI)

Create `services/api/.env`:

```bash
# Supabase Configuration
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_ANON_KEY=your-anon-key-here
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key-here
SUPABASE_JWT_SECRET=your-jwt-secret-here

# Backend Configuration
PORT=8000
```

**Security Notes:**
- Never commit `.env` to git
- Add `.env` to `.gitignore`
- Use environment variables in production (Render, Railway, etc.)

---

## Step 5: Configure Flutter App

### Option A: Development (app_config.dart)

Edit [apps/mobile/lib/config/app_config.dart](apps/mobile/lib/config/app_config.dart):

```dart
class Config {
  static const String supabaseUrl = 'https://xxxxx.supabase.co';
  static const String supabaseAnonKey = 'your-anon-key-here';
  static const String apiBaseUrl = 'http://localhost:8000'; // or Render URL
}
```

### Option B: Production (--dart-define)

```bash
flutter run \
  --dart-define=SUPABASE_URL=https://xxxxx.supabase.co \
  --dart-define=SUPABASE_ANON_KEY=your-anon-key \
  --dart-define=API_BASE_URL=https://savo-ynp1.onrender.com
```

---

## Step 6: Enable Authentication Methods

1. Go to **Authentication** → **Providers** in Supabase Dashboard

### Email Authentication
2. Enable **Email**
3. Configuration:
   - **Enable email confirmations:** OFF (for development)
   - **Secure email change:** ON
   - **Enable email OTP:** ON (for magic link login)

### OAuth Providers (Optional)
4. Enable **Google** (if desired):
   - Get OAuth credentials from Google Cloud Console
   - Add Client ID and Secret
5. Enable **Apple** (if desired):
   - Configure Apple Sign In (iOS only)

---

## Step 7: Configure Row Level Security (RLS)

RLS policies are created by migration files, but verify:

1. Go to **Database** → **Tables** in Supabase Dashboard
2. For each table, click **...** → **Edit table**
3. Verify **Enable Row Level Security** is ON
4. Click **Policies** tab

### Expected Policies

**users table:**
- Users can view own record
- Users can update own record

**household_profiles table:**
- Users can view own household
- Users can create own household
- Users can update own household

**family_members table:**
- Users can view own household members
- Users can create members for own household
- Users can update own household members
- Users can delete own household members

**audit_log table:**
- Users can view own audit logs
- Only service role can insert (backend only)

---

## Step 8: Test Database Connection

### From Backend (Python)

```python
# services/api/test_database.py
import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase: Client = create_client(url, key)

# Test query
result = supabase.table("users").select("*").limit(1).execute()
print(f"Connection successful! {len(result.data)} rows")
```

Run:
```bash
cd services/api
python test_database.py
```

### From Flutter

```dart
// In a test screen
final response = await Supabase.instance.client
  .from('users')
  .select('*')
  .limit(1);
  
print('Connection successful! ${response.length} rows');
```

---

## Step 9: Create Test User

### Option A: Supabase Dashboard

1. Go to **Authentication** → **Users**
2. Click **Add user**
3. Enter:
   - **Email:** test@example.com
   - **Password:** testpassword123
   - **Auto confirm email:** ON
4. Click **Create user**

### Option B: Flutter App (Sign Up)

```dart
final authService = AuthService();
await authService.signUp(
  email: 'test@example.com',
  password: 'testpassword123',
);
```

### Option C: API Call

```bash
curl -X POST 'https://xxxxx.supabase.co/auth/v1/signup' \
  -H "apikey: your-anon-key" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "testpassword123"
  }'
```

---

## Step 10: Test Authentication Flow

### 1. Sign In (Flutter)

```dart
final authService = AuthService();
final response = await authService.signInWithPassword(
  email: 'test@example.com',
  password: 'testpassword123',
);

print('User ID: ${response.user?.id}');
print('Token: ${authService.accessToken}');
```

### 2. Test API Call with Token

```dart
final apiClient = ApiClient();
final profile = await apiClient.get('/profile/household');
print('Profile: $profile');
```

### 3. Verify Backend Receives Token

Check backend logs - should see:
```
INFO: Validated JWT for user: xxxxx-xxxxx-xxxxx
```

---

## Step 11: Verify RLS Policies Work

### Test: User Can Only Access Own Data

1. Create two test users in Supabase
2. Sign in as User A
3. Create household profile for User A
4. Try to access User B's household (should fail)

```dart
// Sign in as User A
await authService.signInWithPassword(
  email: 'userA@example.com',
  password: 'password',
);

// Create household for User A
await profileService.createHouseholdProfile(
  region: 'US',
  primaryLanguage: 'en-US',
);

// Get User A's profile (should work)
final profile = await profileService.getHouseholdProfile();
print('User A profile: $profile');

// Sign in as User B
await authService.signOut();
await authService.signInWithPassword(
  email: 'userB@example.com',
  password: 'password',
);

// Try to get User A's profile (should return empty/error)
final profileB = await profileService.getHouseholdProfile();
print('User B profile (should be empty): $profileB');
```

---

## Step 12: Production Deployment

### Backend (Render, Railway, etc.)

Set environment variables:
```bash
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
SUPABASE_JWT_SECRET=your-jwt-secret
```

### Flutter (CI/CD)

Build command:
```bash
flutter build apk \
  --dart-define=SUPABASE_URL=$SUPABASE_URL \
  --dart-define=SUPABASE_ANON_KEY=$SUPABASE_ANON_KEY \
  --dart-define=API_BASE_URL=$API_BASE_URL
```

---

## Common Issues

### Issue: "Invalid API key"
**Solution:** Check `SUPABASE_ANON_KEY` is correct (from Settings → API)

### Issue: "JWT verification failed"
**Solution:** Ensure backend `SUPABASE_JWT_SECRET` matches Supabase JWT Secret

### Issue: "Row Level Security policy violation"
**Solution:** Verify RLS policies are configured correctly (Step 7)

### Issue: "Table does not exist"
**Solution:** Run migrations (Step 2)

### Issue: "Session expired"
**Solution:** Enable auto-refresh in Flutter main.dart (already done in Phase D)

---

## Monitoring & Logs

### Supabase Dashboard Logs

1. Go to **Logs** → **Auth Logs** to see login attempts
2. Go to **Logs** → **API Logs** to see database queries
3. Go to **Database** → **Table Editor** to view data

### Useful Queries

**Check if user has household profile:**
```sql
SELECT u.email, hp.id AS household_id, hp.onboarding_completed_at
FROM users u
LEFT JOIN household_profiles hp ON hp.user_id = u.id;
```

**Check audit log:**
```sql
SELECT * FROM audit_log
ORDER BY created_at DESC
LIMIT 10;
```

**Check family members:**
```sql
SELECT fm.name, fm.age, fm.allergens, hp.user_id
FROM family_members fm
JOIN household_profiles hp ON fm.household_profile_id = hp.id
ORDER BY fm.created_at DESC;
```

---

## Security Checklist

- [ ] RLS enabled on all tables
- [ ] JWT Secret kept secure (not in git)
- [ ] Service role key only used in backend (never in Flutter)
- [ ] Anon key is public (safe to use in Flutter)
- [ ] Email confirmations configured for production
- [ ] Password policies enforced (min length, complexity)
- [ ] Rate limiting enabled (Supabase defaults)
- [ ] Audit logging working (test allergen update)

---

## Next Steps

With Supabase configured:
1. ✅ Run backend with Supabase connection
2. ✅ Test authentication in Flutter
3. ✅ Verify RLS policies
4. 🔄 Implement onboarding UI (Phase E)
5. 🔄 Add login/signup screens
6. 🔄 Deploy to production

---

**Supabase Setup: ✅ COMPLETE**

Your database is ready for production use!
