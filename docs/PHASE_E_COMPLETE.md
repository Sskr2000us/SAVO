# Phase E: Flutter Onboarding UI - COMPLETE

**Status**: ✅ Complete  
**Date**: 2025-01-XX

## Overview

Phase E implements the complete Flutter UI for the user onboarding flow, including 8 screens that guide users through profile setup with full backend integration, partial completion support, and resume functionality.

## Architecture

### State Management
- **Provider Pattern**: `ProfileState` (ChangeNotifier) holds all profile data
- **Global State**: Single source of truth for profile, onboarding status, user data
- **Reactive Updates**: All screens listen to ProfileState changes

### Navigation Flow
```
AppStartup
  ├─> OnboardingCoordinator (check status)
  │     ├─> LOGIN (Supabase auth)
  │     ├─> HOUSEHOLD (add members)
  │     ├─> ALLERGIES (blocking)
  │     ├─> DIETARY (blocking)
  │     ├─> SPICE (optional)
  │     ├─> PANTRY (optional)
  │     ├─> LANGUAGE (optional)
  │     └─> COMPLETE (finalize)
  └─> MainNavigationShell (if onboarding complete)
```

## Implementation Details

### 1. Core Models

#### ProfileState (`lib/models/profile_state.dart`)
```dart
class ProfileState extends ChangeNotifier {
  Map<String, dynamic>? _profileData;
  Map<String, dynamic>? _onboardingStatus;
  
  // Accessors for all profile data
  String? get householdName;
  List<dynamic> get members;
  List<String> get declaredAllergens;
  bool get isVegetarian;
  String? get preferredLanguage;
  
  // Onboarding helpers
  bool isStepComplete(String step);
  String? get resumeStep;
}
```

**Features**:
- Centralized state management
- Type-safe accessors
- Onboarding status tracking
- Step completion checks

### 2. Navigation Coordinator

#### OnboardingCoordinator (`lib/screens/onboarding/onboarding_coordinator.dart`)
```dart
class OnboardingCoordinator extends StatefulWidget {
  // Checks onboarding status on init
  // Routes to appropriate screen based on resume_step
  // Handles navigation between screens
}

// Helper functions
void navigateToNextOnboardingStep(context, currentStep);
double getOnboardingProgress(step);
String getStepNumber(step);
```

**Features**:
- Auto-resume from last incomplete step
- Progress tracking
- Step-based routing
- Navigation helpers for all screens

### 3. Onboarding Screens

#### Screen 1: LOGIN (`login_screen.dart`)
**Purpose**: User authentication via Supabase  
**Flow**:
1. Email/password sign in OR OTP magic link
2. On success: fetch profile + onboarding status
3. Navigate to HOUSEHOLD or resume_step

**Features**:
- Dual auth methods (password + OTP)
- Session persistence
- Auto-navigation to resume point
- Error handling

**Backend Calls**:
- `AuthService.signInWithPassword()`
- `AuthService.sendOtpLink()`
- `ProfileService.getFullProfile()`
- `ProfileService.getOnboardingStatus()`

---

#### Screen 2: HOUSEHOLD (`household_screen.dart`)
**Purpose**: Add family members  
**Flow**:
1. Display existing members (if any)
2. Add member form: name, age, role, food_name
3. POST to `/profile/members` for each
4. Refetch profile
5. Navigate to ALLERGIES

**Features**:
- Dynamic member list
- Role selection (parent/child/other)
- Optional food_name field
- Remove member capability
- "Save & Exit" support

**Backend Calls**:
- `ProfileService.createFamilyMember()`
- `ProfileService.getFullProfile()`
- `ProfileService.getOnboardingStatus()`

**Validation**:
- Name required (2-50 chars)
- Age must be 0-120
- Role required

---

#### Screen 3: ALLERGIES (`allergies_screen.dart`)
**Purpose**: Declare allergens (blocking)  
**Flow**:
1. Display common allergen chips
2. Multi-select allergens
3. PATCH to `/profile/allergens` with reason
4. Refetch profile
5. Navigate to DIETARY

**Features**:
- Common allergens: peanuts, tree nuts, dairy, eggs, soy, wheat, fish, shellfish
- Multi-select with visual feedback
- Audit logging (reason: "Initial onboarding")
- Applies to all household members
- "Save & Exit" support

**Backend Calls**:
- `ProfileService.updateAllergens(allergensList, reason)`
- `ProfileService.getFullProfile()`

**Validation**:
- Can be empty (no allergens)
- Prevents duplicates

---

#### Screen 4: DIETARY (`dietary_screen.dart`)
**Purpose**: Declare dietary restrictions  
**Flow**:
1. Display dietary restriction checkboxes
2. Multi-select restrictions
3. Validate vegan→vegetarian logic
4. PATCH to `/profile/dietary` for each member
5. Refetch profile
6. Navigate to SPICE

**Features**:
- Options: vegetarian, vegan, no beef, no pork, no alcohol
- Auto-check vegetarian when vegan selected
- Applies to all household members
- "Save & Exit" support

**Backend Calls**:
- `ProfileService.updateDietary(memberId, restrictions)` (for each member)
- `ProfileService.getFullProfile()`

**Validation**:
- Vegan implies vegetarian
- Multiple restrictions allowed

---

#### Screen 5: SPICE (`spice_screen.dart`)
**Purpose**: Set spice tolerance (optional)  
**Flow**:
1. Display spice level options
2. Single-select tolerance
3. PATCH to `/profile/members/:id` for first member
4. Refetch profile
5. Navigate to PANTRY

**Features**:
- Options: none, mild, medium, high, very_high
- Visual emoji indicators (🌶️🔥)
- Skip button with no default
- Applies to first member only (MVP)
- Optional step

**Backend Calls**:
- `ProfileService.updateFamilyMember(memberId, {spice_tolerance})`
- `ProfileService.getFullProfile()`

---

#### Screen 6: PANTRY (`pantry_screen.dart`)
**Purpose**: Check basic spices availability (optional)  
**Flow**:
1. Display yes/no options
2. Single-select
3. PATCH to `/profile/preferences`
4. Refetch profile
5. Navigate to LANGUAGE

**Features**:
- Binary choice: has basic spices or needs to buy
- Skip button with no default
- Affects shopping list generation
- Optional step

**Backend Calls**:
- `ProfileService.updatePreferences(basicSpicesAvailable: bool)`
- `ProfileService.getFullProfile()`

---

#### Screen 7: LANGUAGE (`language_screen.dart`)
**Purpose**: Set language and measurement system (optional)  
**Flow**:
1. Display language dropdown (10 languages)
2. Display measurement system (metric/imperial)
3. PATCH to `/profile/language`
4. Refetch profile
5. Navigate to COMPLETE

**Features**:
- 10 languages with flag emojis
- Metric vs Imperial units
- Skip button (defaults to device locale)
- Optional step

**Backend Calls**:
- `ProfileService.updateLanguage(preferredLanguage, measurementSystem)`
- `ProfileService.getFullProfile()`

**Supported Languages**:
- English (en), Español (es), Français (fr), Deutsch (de), Italiano (it)
- Português (pt), 中文 (zh), 日本語 (ja), 한국어 (ko), हिन्दी (hi)

---

#### Screen 8: COMPLETE (`complete_screen.dart`)
**Purpose**: Finalize onboarding  
**Flow**:
1. Display success message + summary
2. Show household name, member count, allergen count
3. "Start Cooking" button
4. PATCH to `/profile/complete`
5. Refetch profile
6. Navigate to /home (replace stack)

**Features**:
- Success animation (checkmark icon)
- Profile summary cards
- No "Save & Exit" (final step)
- Clears navigation stack

**Backend Calls**:
- `ProfileService.completeOnboarding()`
- `ProfileService.getFullProfile()`

**UI Components**:
- Celebration UI
- Summary cards (members, allergens)
- Primary CTA button

---

## Shared Patterns

### Every Screen Follows
```dart
1. Load existing data from ProfileState in initState()
2. Collect user input via form/widgets
3. Validate input locally
4. Call ProfileService API method
5. Refetch getFullProfile() to get updated data
6. Update ProfileState with new data
7. Call navigateToNextOnboardingStep()
```

### Error Handling
- Try/catch around all API calls
- Display errors in red banner
- Keep form data on error
- User can retry

### Progress Tracking
- Linear progress bar at top
- "Step X of 8" indicator
- Step numbers via `getStepNumber()`
- Progress percentage via `getOnboardingProgress()`

### Save & Exit
- All screens except LOGIN and COMPLETE
- Saves current progress to backend
- User can resume later from same step
- Backend tracks `resume_step`

## App Launch Flow

### AppStartupScreen (`main.dart`)
```dart
1. Check Supabase session
   - No session → navigate to /onboarding (LOGIN)
   - Has session → check onboarding status

2. If has session:
   - Call getOnboardingStatus()
   - Load getFullProfile()
   - Update ProfileState
   - If completed=true → navigate to /home
   - If completed=false → navigate to /onboarding (resume_step)

3. OnboardingCoordinator routes to correct screen
```

## Backend Integration

### API Endpoints Used

| Endpoint | Method | Purpose | Screen |
|----------|--------|---------|--------|
| `/auth/login` | POST | Email/password auth | LOGIN |
| `/auth/otp` | POST | Send OTP link | LOGIN |
| `/profile/full` | GET | Fetch all profile data | All |
| `/profile/onboarding-status` | GET | Check completion | All |
| `/profile/members` | POST | Create family member | HOUSEHOLD |
| `/profile/allergens` | PATCH | Update allergens | ALLERGIES |
| `/profile/dietary` | PATCH | Update dietary | DIETARY |
| `/profile/members/:id` | PATCH | Update member | SPICE |
| `/profile/preferences` | PATCH | Update prefs | PANTRY |
| `/profile/language` | PATCH | Update language | LANGUAGE |
| `/profile/complete` | PATCH | Mark complete | COMPLETE |

### Response Patterns

**GET /profile/full**:
```json
{
  "user": {"id": "...", "email": "..."},
  "household": {"name": "Smith Family", "primary_language": "en", ...},
  "profile": {...},
  "members": [{"id": "...", "name": "Alice", ...}],
  "allergens": {"declared_allergens": ["peanuts"]},
  "dietary": {"vegetarian": true, ...}
}
```

**GET /profile/onboarding-status**:
```json
{
  "completed": false,
  "resume_step": "DIETARY",
  "missing_fields": ["dietary_restrictions"],
  "steps_completed": ["HOUSEHOLD", "ALLERGIES"]
}
```

## Testing Guide

### Manual Testing Flow

1. **Fresh Install**:
   ```
   AppStartup → LOGIN (no session)
   ```

2. **Login with Email/Password**:
   ```
   Enter credentials → Success → HOUSEHOLD
   ```

3. **Add Family Members**:
   ```
   Add 2 members → Next → ALLERGIES
   ```

4. **Declare Allergens**:
   ```
   Select peanuts, dairy → Next → DIETARY
   ```

5. **Set Dietary Restrictions**:
   ```
   Check vegetarian → Next → SPICE
   ```

6. **Save & Exit** (Test Resume):
   ```
   Press "Save & Exit" → Closes app
   Reopen app → AppStartup → SPICE (resumes)
   ```

7. **Complete Remaining Steps**:
   ```
   SPICE → Skip → PANTRY → Skip → LANGUAGE → Skip → COMPLETE
   ```

8. **Finalize**:
   ```
   Press "Start Cooking" → /home (MainNavigationShell)
   ```

9. **Reopen App** (Test Complete):
   ```
   AppStartup → /home (already complete)
   ```

### Unit Test Checklist

- [ ] ProfileState updates correctly
- [ ] navigateToNextOnboardingStep() routing
- [ ] getOnboardingProgress() calculations
- [ ] isStepComplete() logic for each step
- [ ] Error handling in API calls
- [ ] Form validation (name, age, email)
- [ ] Vegan→vegetarian auto-check
- [ ] Skip button behavior

### Integration Test Checklist

- [ ] Full onboarding flow (LOGIN → COMPLETE)
- [ ] Save & Exit at each step
- [ ] Resume from each step
- [ ] Backend data persistence
- [ ] Session persistence across app restarts
- [ ] Navigation stack management
- [ ] Error recovery

## File Structure

```
lib/
├── main.dart                          # Added AppStartupScreen, ProfileState provider
├── models/
│   └── profile_state.dart            # ✅ Complete ChangeNotifier model
├── services/
│   ├── auth_service.dart             # Phase D (Supabase auth)
│   ├── profile_service.dart          # Phase D (API client)
│   └── api_client.dart               # Phase D (HTTP client)
└── screens/
    └── onboarding/
        ├── onboarding_coordinator.dart   # ✅ Navigation coordinator
        ├── login_screen.dart             # ✅ Screen 1: Auth
        ├── household_screen.dart         # ✅ Screen 2: Members
        ├── allergies_screen.dart         # ✅ Screen 3: Allergens
        ├── dietary_screen.dart           # ✅ Screen 4: Restrictions
        ├── spice_screen.dart             # ✅ Screen 5: Tolerance
        ├── pantry_screen.dart            # ✅ Screen 6: Spices
        ├── language_screen.dart          # ✅ Screen 7: Lang/Units
        └── complete_screen.dart          # ✅ Screen 8: Finalize
```

## Key Features Implemented

✅ **8 Complete Onboarding Screens**
- LOGIN (auth), HOUSEHOLD (members), ALLERGIES, DIETARY, SPICE, PANTRY, LANGUAGE, COMPLETE

✅ **State Management**
- ProfileState ChangeNotifier
- Global state with Provider
- Reactive UI updates

✅ **Navigation**
- OnboardingCoordinator with step routing
- Progress tracking
- Auto-resume from last step

✅ **Backend Integration**
- All 11 API endpoints connected
- Refetch pattern after mutations
- Error handling

✅ **Partial Completion**
- "Save & Exit" on 6 screens
- Backend tracks resume_step
- Auto-resume on app reopen

✅ **Session Management**
- Supabase JWT with auto-refresh
- Session persistence
- App launch checks

✅ **UI/UX**
- Material Design 3
- Progress indicators
- Error banners
- Loading states
- Skip buttons for optional steps

## Configuration

### Required Environment
- Supabase URL and anon key in `lib/config/app_config.dart`
- Backend API running (Phase C endpoints)
- Database with Phase A schema

### Dependencies (pubspec.yaml)
```yaml
dependencies:
  flutter: sdk: flutter
  provider: ^6.1.0
  supabase_flutter: ^2.3.0
  http: ^1.2.0
```

## Known Limitations (MVP)

1. **Spice Tolerance**: Only applied to first member (not per-member)
2. **Language**: Single language per household (no per-member)
3. **Offline**: No offline support (requires network)
4. **Validation**: Basic client-side validation (server also validates)
5. **Accessibility**: Screen reader support not yet implemented
6. **Localization**: UI strings not yet externalized (en only)

## Next Steps (Post-MVP)

1. **Phase F**: Home Screen with Recipe Recommendations
2. **Phase G**: Weekly Planner with Batch Cooking
3. **Phase H**: Cook Mode with Step-by-Step
4. **Phase I**: Leftover Tracking + Reminders
5. **Phase J**: Settings Screen with Profile Editing

## Troubleshooting

### Issue: "No session" error
- **Cause**: Supabase session expired
- **Fix**: Re-login via LOGIN screen

### Issue: Stuck on loading screen
- **Cause**: Backend API not reachable
- **Fix**: Check backend is running, check API URL in config

### Issue: Profile data not loading
- **Cause**: API error or no profile exists
- **Fix**: Check backend logs, ensure migration ran

### Issue: Resume not working
- **Cause**: Session lost or backend not updating resume_step
- **Fix**: Check backend `/profile/onboarding-status` endpoint

## Success Criteria

✅ All 8 screens implemented  
✅ Backend integration complete  
✅ Save & Exit works on 6 screens  
✅ Resume from any step works  
✅ Session persistence works  
✅ Navigation flow correct  
✅ Error handling present  
✅ Progress tracking visible  
✅ Manual testing passed  

**Phase E Status**: 🎉 **COMPLETE**

## Related Documentation

- [Phase A: Database Setup](../docs/user_profile.md#phase-a)
- [Phase B: Backend Auth](../docs/user_profile.md#phase-b)
- [Phase C: Backend API](../docs/user_profile.md#phase-c)
- [Phase D: Flutter SDK](../docs/user_profile.md#phase-d)
- [Testing Guide](../TESTING_GUIDE.md)
- [Architecture](../docs/COMPLETE_ARCHITECTURE.md)
