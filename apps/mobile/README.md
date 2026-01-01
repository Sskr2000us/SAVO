# SAVO Mobile App

Flutter mobile application for SAVO meal planning and cooking assistant.

## Features

✅ **User Profile Management** - Household setup, family members, allergens, dietary restrictions
✅ **Supabase Authentication** - JWT-based auth with session persistence
✅ **Onboarding Flow** - Step-by-step profile setup with resume capability
✅ **Meal Planning** - AI-powered recipe recommendations
✅ **Inventory Management** - Track ingredients and leftovers
✅ **Cooking Mode** - Step-by-step recipe guidance

## Getting Started

### Prerequisites
- Flutter SDK 3.2.0 or higher
- Dart 3.0 or higher
- Supabase account (free tier works)

### Installation

1. **Install dependencies:**
```bash
flutter pub get
```

2. **Configure Supabase:**

Edit `lib/config/app_config.dart` with your credentials:
```dart
static const String supabaseUrl = 'https://YOUR_PROJECT.supabase.co';
static const String supabaseAnonKey = 'YOUR_ANON_KEY';
```

Get these from: Supabase Dashboard → Settings → API

3. **Run the app:**
```bash
flutter run
```

See [QUICK_START.md](QUICK_START.md) for detailed setup instructions.

## Project Structure

```
lib/
├── config/
│   └── app_config.dart          # Environment configuration
├── screens/
│   ├── home_screen.dart         # Home dashboard
│   ├── plan_screen.dart         # Meal planning
│   ├── cook_screen.dart         # Cooking mode
│   ├── leftovers_screen.dart    # Leftover management
│   └── settings_screen.dart     # User settings
├── services/
│   ├── api_client.dart          # HTTP client with auto Bearer token
│   ├── auth_service.dart        # Supabase authentication
│   └── profile_service.dart     # Profile API endpoints
└── theme/
    └── app_theme.dart           # Dark theme
```

## Authentication

The app uses Supabase for authentication with:
- Email/password login
- Magic link (OTP) login
- JWT Bearer tokens for API calls
- Automatic session persistence
- Token refresh on app resume

Example:
```dart
final authService = Provider.of<AuthService>(context, listen: false);

// Sign in
await authService.signInWithPassword(
  email: 'user@example.com',
  password: 'password123',
);

// Check auth status
if (authService.isAuthenticated) {
  print('User ID: ${authService.userId}');
}

// Sign out
await authService.signOut();
```

## Profile Management

Complete profile management with Phase C backend endpoints:

```dart
final profileService = ProfileService(apiClient);

// Get full profile
final profile = await profileService.getFullProfile();

// Update allergens (with audit logging)
await profileService.updateAllergens(
  memberId: 'uuid',
  allergens: ['peanuts', 'shellfish'],
  reason: 'Doctor confirmed',
);

// Check onboarding status
final status = await profileService.getOnboardingStatus();
print('Resume at: ${status['resume_step']}');

// Complete onboarding
await profileService.completeOnboarding();
```

## Development

### Backend API
The app connects to the FastAPI backend deployed on Render:
- Production: `https://savo-ynp1.onrender.com`
- Local: `http://localhost:8000` (update in app_config.dart)

### Running Locally
1. Start backend: `cd ../../services/api && uvicorn app.main:app --reload`
2. Update `apiBaseUrl` in app_config.dart to `http://localhost:8000`
3. Run Flutter: `flutter run`

### Testing
```bash
flutter test
```

## Documentation

- [QUICK_START.md](QUICK_START.md) - Quick setup guide
- [../../PHASE_D_COMPLETE.md](../../PHASE_D_COMPLETE.md) - Phase D implementation details
- [../../SUPABASE_SETUP_GUIDE.md](../../SUPABASE_SETUP_GUIDE.md) - Supabase configuration
- [../../API_ENDPOINTS_REFERENCE.md](../../API_ENDPOINTS_REFERENCE.md) - Backend API reference
- [../../user_profile.md](../../user_profile.md) - Complete implementation plan

## Implementation Status

### ✅ Phase D Complete (Flutter SDK Integration)
- Supabase SDK integrated
- JWT authentication
- Session persistence
- ProfileService for all endpoints
- Bearer token auto-injection

### 🔄 Phase E Next (Onboarding UI)
- LOGIN screen
- HOUSEHOLD screen (family members)
- ALLERGIES screen (with safety confirmation)
- DIETARY screen (restrictions)
- SPICE screen (tolerance)
- PANTRY screen (basic spices)
- LANGUAGE screen (language + measurement)
- COMPLETE screen

## Resources

- [Flutter Documentation](https://docs.flutter.dev/)
- [Supabase Flutter SDK](https://supabase.com/docs/reference/dart/introduction)
- [SAVO Backend API](https://savo-ynp1.onrender.com/docs)

## License

Private project - All rights reserved.
