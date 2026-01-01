# Phase D: Flutter Supabase SDK Integration - COMPLETE ✅

## Overview
Phase D adds Supabase SDK to the Flutter mobile app, enabling JWT-based authentication, session persistence, and secure API communication with Bearer tokens.

## What Was Implemented

### 1. Dependencies Added (pubspec.yaml)
```yaml
supabase_flutter: ^2.3.0
flutter_secure_storage: ^9.0.0  # Used by Supabase for secure session storage
```

### 2. Configuration (app_config.dart)
Created centralized configuration:
- `SUPABASE_URL` - Your Supabase project URL
- `SUPABASE_ANON_KEY` - Your Supabase anonymous key
- `API_BASE_URL` - Backend API URL (defaults to Render deployment)

### 3. Main App Initialization (main.dart)
- **Supabase SDK initialization** with `persistSession: true`
- **PKCE auth flow** for secure mobile authentication
- **Auto token refresh** enabled
- **App lifecycle observer** to refresh session when app resumes
- **Multi-provider setup** for ApiClient and AuthService

### 4. AuthService (auth_service.dart)
Comprehensive authentication service:

**Sign In Methods:**
- `signInWithPassword()` - Email + password
- `signInWithOtp()` - Magic link / OTP
- `verifyOtp()` - Verify OTP code
- `signUp()` - Create new account

**Session Management:**
- `currentUser` - Get current user
- `accessToken` - Get JWT token for API calls
- `isAuthenticated` - Check auth status
- `refreshSession()` - Manually refresh token
- `signOut()` - Sign out current device
- `signOutOtherDevices()` - Sign out all except current

**Utilities:**
- `authStateChanges` - Stream of auth state changes
- `updateUser()` - Update user metadata
- `getDeviceInfo()` - Get device info for audit logging

### 5. API Client Updates (api_client.dart)
- **Automatic Bearer token injection** via `_getAuthHeaders()`
- **All HTTP methods updated** (GET, POST, PATCH, PUT, DELETE, multipart)
- **Removed hardcoded X-User-Id** headers
- **Token automatically added** to all requests when authenticated

### 6. ProfileService (profile_service.dart)
Complete service for all Phase C endpoints:

**Full Profile:**
- `getFullProfile()` - Get complete user state

**Household Management:**
- `getHouseholdProfile()`
- `createHouseholdProfile()`
- `updateHouseholdProfile()`

**Family Members:**
- `getFamilyMembers()`
- `createFamilyMember()`
- `updateFamilyMember()`
- `deleteFamilyMember()`

**Specialized Updates (Phase C):**
- `updateAllergens()` - With audit logging
- `updateDietary()` - Dietary restrictions
- `updatePreferences()` - Cuisines, spices, pantry
- `updateLanguage()` - Primary language

**Onboarding:**
- `getOnboardingStatus()` - Check completion
- `completeOnboarding()` - Mark complete
- `isOnboardingComplete()` - Helper
- `getResumeStep()` - Get resume step

**Helpers:**
- `writeAndRefetch()` - Write + refetch pattern

---

## Setup Instructions

### Step 1: Get Supabase Credentials

1. Go to your Supabase project dashboard
2. Navigate to **Settings** → **API**
3. Copy these values:
   - **Project URL** (e.g., `https://xxxxx.supabase.co`)
   - **anon public key** (starts with `eyJ...`)

### Step 2: Configure Environment

Create a `.env` file in `apps/mobile/`:

```env
# Supabase Configuration
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_ANON_KEY=your-anon-key-here

# Backend API
API_BASE_URL=https://savo-ynp1.onrender.com
```

### Step 3: Update app_config.dart

Replace the default values in [lib/config/app_config.dart](lib/config/app_config.dart):

```dart
class Config {
  static const String supabaseUrl = String.fromEnvironment(
    'SUPABASE_URL',
    defaultValue: 'https://your-project-id.supabase.co',  // ← Your URL
  );
  
  static const String supabaseAnonKey = String.fromEnvironment(
    'SUPABASE_ANON_KEY',
    defaultValue: 'your-anon-key-here',  // ← Your key
  );
  
  static const String apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'https://savo-ynp1.onrender.com',
  );
}
```

### Step 4: Install Dependencies

```bash
cd apps/mobile
flutter pub get
```

### Step 5: Update Backend JWT Secret

Ensure your backend has the correct JWT secret:

```bash
# In services/api/.env
SUPABASE_JWT_SECRET=your-jwt-secret-from-supabase-api-settings
```

Get this from: Supabase Dashboard → Settings → API → JWT Secret

---

## Usage Examples

### 1. Sign In with Email/Password

```dart
import 'package:provider/provider.dart';
import 'package:savo/services/auth_service.dart';

// In your widget
final authService = Provider.of<AuthService>(context, listen: false);

try {
  final response = await authService.signInWithPassword(
    email: 'user@example.com',
    password: 'password123',
  );
  
  print('Logged in: ${response.user?.email}');
  print('Token: ${authService.accessToken}');
} catch (e) {
  print('Login failed: $e');
}
```

### 2. Sign In with Magic Link (OTP)

```dart
// Step 1: Request OTP
await authService.signInWithOtp(email: 'user@example.com');
print('Check your email for OTP code');

// Step 2: User enters code, verify it
final response = await authService.verifyOtp(
  email: 'user@example.com',
  token: '123456',  // User-entered code
);
```

### 3. Check Auth Status

```dart
if (authService.isAuthenticated) {
  print('User ID: ${authService.userId}');
  print('Token: ${authService.accessToken}');
} else {
  // Navigate to login
}
```

### 4. Listen to Auth State Changes

```dart
authService.authStateChanges.listen((AuthState state) {
  switch (state.event) {
    case AuthChangeEvent.signedIn:
      print('User signed in: ${state.session?.user.email}');
      // Navigate to home
      break;
    case AuthChangeEvent.signedOut:
      print('User signed out');
      // Navigate to login
      break;
    case AuthChangeEvent.tokenRefreshed:
      print('Token refreshed');
      break;
  }
});
```

### 5. Use ProfileService

```dart
import 'package:provider/provider.dart';
import 'package:savo/services/profile_service.dart';
import 'package:savo/services/api_client.dart';

// Create service
final apiClient = Provider.of<ApiClient>(context, listen: false);
final profileService = ProfileService(apiClient);

// Get full profile
final profile = await profileService.getFullProfile();
print('User: ${profile['user']}');
print('Household: ${profile['household']}');
print('Members: ${profile['members']}');
print('Allergens: ${profile['allergens']}');

// Check onboarding status
final status = await profileService.getOnboardingStatus();
if (status['completed'] == false) {
  final resumeStep = status['resume_step'];
  print('Resume onboarding at: $resumeStep');
  // Navigate to onboarding screen
}

// Update allergens (with audit)
await profileService.updateAllergens(
  memberId: 'member-uuid',
  allergens: ['peanuts', 'shellfish'],
  reason: 'Doctor confirmed',
);

// Refetch after update
final updatedProfile = await profileService.getFullProfile();
```

### 6. Write and Refetch Pattern

```dart
// Automatically refetch after any write
final updatedProfile = await profileService.writeAndRefetch(() async {
  return await profileService.updatePreferences(
    favoriteCuisines: ['Italian', 'Thai', 'Mexican'],
    basicSpicesAvailable: true,
  );
});

// updatedProfile now has latest data from backend
```

### 7. Sign Out

```dart
// Sign out current device
await authService.signOut();

// Sign out all other devices (keep current logged in)
await authService.signOutOtherDevices();
```

---

## Session Persistence

Session is automatically persisted using `flutter_secure_storage`:
- **App restart**: User stays logged in
- **App resume**: Token automatically refreshed if needed
- **Token expiry**: Auto-refresh every hour (Supabase default)

### Refresh Behavior

The app automatically refreshes the session when:
1. App returns to foreground (resume)
2. Token is about to expire (auto-refresh enabled)
3. Manual call to `authService.refreshSession()`

### Session Failure Handling

If session refresh fails (e.g., token revoked):
1. User is logged out
2. Session is cleared
3. App should navigate to login screen

Example:

```dart
@override
void didChangeAppLifecycleState(AppLifecycleState state) {
  if (state == AppLifecycleState.resumed) {
    _refreshSession();
  }
}

Future<void> _refreshSession() async {
  try {
    final session = Supabase.instance.client.auth.currentSession;
    if (session != null) {
      await Supabase.instance.client.auth.refreshSession();
    }
  } catch (e) {
    // Session refresh failed - navigate to login
    if (mounted) {
      Navigator.of(context).pushReplacementNamed('/login');
    }
  }
}
```

---

## Removing Old X-User-Id Headers

The following files still have hardcoded `X-User-Id` headers that should be removed:

1. [lib/screens/scan_ingredients_screen.dart](lib/screens/scan_ingredients_screen.dart) - Line 127
2. [lib/screens/settings_screen.dart](lib/screens/settings_screen.dart) - Lines 53, 61, 117, 173
3. [lib/screens/inventory_screen.dart](lib/screens/inventory_screen.dart) - Lines 35, 71, 147

**Migration Steps:**
1. Ensure user is authenticated (has Supabase session)
2. Remove all `'X-User-Id': '...'` headers from API calls
3. Bearer token will be automatically added by ApiClient

Example:

**Before:**
```dart
final response = await apiClient.get('/inventory', headers: {
  'X-User-Id': '00000000-0000-0000-0000-000000000001',  // TODO: Get from auth
});
```

**After:**
```dart
final response = await apiClient.get('/inventory');
// Bearer token automatically added by ApiClient._getAuthHeaders()
```

---

## Security Considerations

✅ **JWT tokens stored securely** via `flutter_secure_storage`
✅ **PKCE auth flow** for mobile security
✅ **Auto token refresh** prevents expiration
✅ **Bearer token never exposed** in logs or UI
✅ **Session isolated per device**

⚠️ **Important:**
- Never log `accessToken` in production
- Never commit `.env` to git (add to `.gitignore`)
- Use environment variables for secrets in CI/CD

---

## Testing Checklist

### Authentication
- [ ] Sign in with email/password
- [ ] Sign in with OTP/magic link
- [ ] Sign up new account
- [ ] Sign out
- [ ] Sign out other devices
- [ ] Session persists after app restart
- [ ] Session refreshes on app resume

### API Calls
- [ ] All endpoints send Bearer token
- [ ] Backend accepts token (no 401 errors)
- [ ] Profile endpoints work (GET /profile/full)
- [ ] Allergen updates log to audit_log
- [ ] Onboarding status calculates correctly

### Error Handling
- [ ] Expired token triggers refresh
- [ ] Invalid token logs user out
- [ ] Network errors show friendly message
- [ ] 401 navigates to login

---

## Next Steps (Phase E)

With Phase D complete, you can now build the onboarding UI:

### Phase E: Flutter Onboarding Screens
1. Create LOGIN screen with Supabase auth
2. Create HOUSEHOLD screen (add members)
3. Create ALLERGIES screen (with audit confirmation)
4. Create DIETARY screen (restrictions)
5. Create SPICE screen (tolerance)
6. Create PANTRY screen (basic spices)
7. Create LANGUAGE screen (measurement system)
8. Create COMPLETE screen (call `completeOnboarding()`)

Each screen should:
- Use `ProfileService` to write data
- Call `getFullProfile()` after each submit
- Update local state with backend response
- Support "Save & Exit" for partial completion

---

## File Structure

```
apps/mobile/
├── lib/
│   ├── main.dart ✨ UPDATED (Supabase init + lifecycle)
│   ├── config/
│   │   └── app_config.dart ✨ NEW (environment config)
│   └── services/
│       ├── api_client.dart ✨ UPDATED (Bearer token auth)
│       ├── auth_service.dart ✨ NEW (Supabase auth wrapper)
│       └── profile_service.dart ✨ NEW (Phase C endpoints)
├── pubspec.yaml ✨ UPDATED (supabase_flutter + flutter_secure_storage)
└── .env ✨ NEW (Supabase credentials - not committed)
```

---

## Troubleshooting

### Issue: "Invalid JWT Secret"
**Solution:** Ensure backend `SUPABASE_JWT_SECRET` matches Supabase dashboard JWT Secret

### Issue: "Session expired"
**Solution:** Check auto-refresh is enabled in main.dart (`autoRefreshToken: true`)

### Issue: "401 Unauthorized"
**Solution:** Verify user is signed in (`authService.isAuthenticated`)

### Issue: "Token not sent"
**Solution:** Check ApiClient._getAuthHeaders() is being called for all requests

---

**Phase D Status: ✅ COMPLETE**

All Flutter infrastructure is ready for onboarding UI implementation (Phase E).
