# Quick Start: Flutter + Supabase Integration

## Install Dependencies

```bash
cd apps/mobile
flutter pub get
```

## Configure Supabase

### 1. Get your credentials from Supabase Dashboard:
- Settings → API → **Project URL**
- Settings → API → **anon public key**

### 2. Update [lib/config/app_config.dart](lib/config/app_config.dart):

```dart
class Config {
  static const String supabaseUrl = 'https://YOUR_PROJECT.supabase.co';
  static const String supabaseAnonKey = 'YOUR_ANON_KEY_HERE';
  static const String apiBaseUrl = 'https://savo-ynp1.onrender.com';
}
```

### 3. Configure backend [services/api/.env](../../services/api/.env):

```bash
SUPABASE_JWT_SECRET=your-jwt-secret-from-supabase
```

## Test Authentication

### Create a test user in Supabase:
1. Go to **Authentication** → **Users** in Supabase Dashboard
2. Click **Add user**
3. Email: `test@example.com`, Password: `testpassword123`
4. Enable **Auto confirm email**

### Test login in Flutter:

```dart
import 'package:provider/provider.dart';
import 'package:savo/services/auth_service.dart';

final authService = Provider.of<AuthService>(context, listen: false);

try {
  await authService.signInWithPassword(
    email: 'test@example.com',
    password: 'testpassword123',
  );
  
  print('✅ Logged in!');
  print('User ID: ${authService.userId}');
  print('Token: ${authService.accessToken}');
} catch (e) {
  print('❌ Login failed: $e');
}
```

## Test Profile API

```dart
import 'package:savo/services/profile_service.dart';

final apiClient = Provider.of<ApiClient>(context, listen: false);
final profileService = ProfileService(apiClient);

// Get full profile
final profile = await profileService.getFullProfile();
print('Profile: $profile');

// Check onboarding status
final status = await profileService.getOnboardingStatus();
print('Onboarding complete: ${status['completed']}');
print('Resume step: ${status['resume_step']}');
```

## Run the App

```bash
flutter run
```

## Common Issues

### "Invalid API key"
→ Check `supabaseAnonKey` in app_config.dart

### "JWT verification failed"  
→ Check backend has correct `SUPABASE_JWT_SECRET`

### "401 Unauthorized"
→ Ensure user is signed in before API calls

## Next: Build Onboarding UI

See [user_profile.md](../../user_profile.md) Phase E for onboarding screen requirements.

---

**Status: ✅ Ready to code!**
