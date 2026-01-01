# Phase F: Onboarding Partial Completion (Resume) - COMPLETE

**Status**: ✅ Complete  
**Date**: 2025-01-01

## Overview

Phase F implements offline-capable onboarding resume functionality using SharedPreferences as a local cache fallback when the backend server is unreachable. This ensures users can continue their onboarding journey even without internet connectivity, with seamless resume from their last completed step.

## Problem Statement

**Challenge**: Users may lose internet connectivity during onboarding or the backend server may be temporarily unavailable. Without offline support, users would need to start onboarding from scratch each time.

**Solution**: Dual-layer persistence strategy:
1. **Primary**: Server-side resume via `GET /profile/onboarding-status` (source of truth)
2. **Fallback**: Local SharedPreferences cache when server is unreachable (offline mode)

## Architecture

### Resume Precedence (Waterfall Logic)

```
1. Try: GET /profile/onboarding-status from server
   ✅ Success → Use server resume_step
   ❌ Fail → Go to step 2

2. Try: OnboardingStorage.getLastStep(userId) from local cache
   ✅ Found → Use cached step (offline mode)
   ❌ Not found → Go to step 3

3. Ultimate Fallback: Start from LOGIN
```

### Data Flow

```
┌─────────────────────────────────────────────────────────┐
│ User completes onboarding step (e.g., HOUSEHOLD)       │
└───────────────────┬─────────────────────────────────────┘
                    │
        ┌───────────┴───────────┐
        │                       │
        ▼                       ▼
┌───────────────┐       ┌──────────────────┐
│ PATCH /api    │       │ saveLastStep()   │
│ (server)      │       │ (local cache)    │
└───────┬───────┘       └────────┬─────────┘
        │                        │
        └────────┬───────────────┘
                 │
                 ▼
        ┌────────────────┐
        │ Navigate Next  │
        └────────────────┘

┌─────────────────────────────────────────────────────────┐
│ User reopens app                                        │
└───────────────────┬─────────────────────────────────────┘
                    │
        ┌───────────┴──────────────┐
        │ Try server status        │
        │ GET /onboarding-status   │
        └───────────┬──────────────┘
                    │
            ┌───────┴────────┐
            │                │
      Success │          Fail │
            │                │
            ▼                ▼
    ┌──────────────┐   ┌──────────────────┐
    │ Use server   │   │ Try local cache  │
    │ resume_step  │   │ getLastStep()    │
    └──────────────┘   └────────┬─────────┘
                                │
                        ┌───────┴────────┐
                        │                │
                  Found │          Null  │
                        │                │
                        ▼                ▼
                ┌──────────────┐   ┌──────────┐
                │ Resume from  │   │ Start at │
                │ cached step  │   │ LOGIN    │
                └──────────────┘   └──────────┘
```

## Implementation Details

### 1. OnboardingStorage Service

**File**: `lib/services/onboarding_storage.dart`

**Features**:
- Step-to-index mapping (1-8)
- User ID validation (prevents cross-user cache pollution)
- Auto-clear on user change
- Completion tracking

**Key Methods**:

```dart
// Save progress after successful API call
await OnboardingStorage.saveLastStep('HOUSEHOLD', userId);

// Get cached step (returns null if user mismatch or no cache)
final cachedStep = await OnboardingStorage.getLastStep(currentUserId);

// Check completion status
final isComplete = await OnboardingStorage.isOnboardingComplete(userId);

// Calculate next step to resume
final resumeStep = OnboardingStorage.getResumeStep('HOUSEHOLD'); // Returns 'ALLERGIES'

// Clear all data (on logout)
await OnboardingStorage.clearOnboardingData();
```

**Storage Keys**:
- `onboarding_last_step` (int): Step index (1-8)
- `onboarding_completed` (bool): Completion flag
- `onboarding_last_user_id` (String): User ID for cache validation

### 2. Screen Updates

All 8 onboarding screens updated to save progress locally after successful API submissions:

#### Pattern Applied to All Screens

```dart
// After successful API call and status update
final userId = profileState.userId;
if (userId != null) {
  await OnboardingStorage.saveLastStep('STEP_NAME', userId);
}

if (mounted) {
  navigateToNextOnboardingStep(context, 'STEP_NAME');
}
```

#### Screens Updated

| Screen | Step Name | Save Location |
|--------|-----------|---------------|
| login_screen.dart | LOGIN | After both auth methods |
| household_screen.dart | HOUSEHOLD | After member creation |
| allergies_screen.dart | ALLERGIES | After allergen update |
| dietary_screen.dart | DIETARY | After dietary update |
| spice_screen.dart | SPICE | After spice update |
| pantry_screen.dart | PANTRY | After pantry update |
| language_screen.dart | LANGUAGE | After language update |
| complete_screen.dart | COMPLETE | After completion API call |

### 3. OnboardingCoordinator Fallback Logic

**File**: `lib/screens/onboarding/onboarding_coordinator.dart`

**Updated**: `_checkOnboardingStatus()` method

**Logic**:
```dart
try {
  // 1. Try server first (primary)
  final status = await profileService.getOnboardingStatus();
  _resumeStep = status['resume_step'];
  // Navigate based on server response
} catch (serverError) {
  // 2. Server failed - try local cache (fallback)
  try {
    final userId = session?.user.id;
    if (userId != null) {
      final cachedStep = await OnboardingStorage.getLastStep(userId);
      final isComplete = await OnboardingStorage.isOnboardingComplete(userId);
      
      if (isComplete) {
        // Go to home
        Navigator.pushReplacementNamed('/home');
      } else if (cachedStep != null) {
        // Resume from cached step
        _resumeStep = OnboardingStorage.getResumeStep(cachedStep);
      }
    }
  } catch (localError) {
    // 3. Ultimate fallback - start from LOGIN
    _resumeStep = 'LOGIN';
  }
}
```

**Behavior**:
- **Online + Server Reachable**: Uses server resume_step (always up-to-date)
- **Offline or Server Down**: Uses local cache (last known good state)
- **No Cache**: Starts from LOGIN

### 4. AppStartupScreen Fallback Logic

**File**: `lib/main.dart`

**Updated**: `_checkAuthAndOnboarding()` method in `AppStartupScreen`

**Logic**:
```dart
// Has session -> check onboarding status
try {
  // 1. Try server (primary)
  final status = await profileService.getOnboardingStatus();
  if (status['completed']) {
    Navigator.pushReplacementNamed('/home');
  } else {
    Navigator.pushReplacementNamed('/onboarding');
  }
} catch (serverError) {
  // 2. Server failed - try local cache (fallback)
  try {
    final isComplete = await OnboardingStorage.isOnboardingComplete(userId);
    if (isComplete) {
      Navigator.pushReplacementNamed('/home'); // Offline - use cache
    } else {
      Navigator.pushReplacementNamed('/onboarding'); // Offline - resume
    }
  } catch (localError) {
    // 3. Ultimate fallback - start onboarding
    Navigator.pushReplacementNamed('/onboarding');
  }
}
```

## User Scenarios

### Scenario 1: Normal Online Flow
1. User completes HOUSEHOLD step
2. App saves to server ✅
3. App saves to local cache ✅
4. User closes app
5. User reopens app
6. Server returns `resume_step: ALLERGIES`
7. App navigates to ALLERGIES screen

### Scenario 2: Offline Mid-Onboarding
1. User completes HOUSEHOLD step (online)
2. App saves to server ✅
3. App saves to local cache ✅
4. User loses internet connection 📴
5. User closes app
6. User reopens app (still offline)
7. Server call fails ❌
8. App reads local cache: `last_step: HOUSEHOLD`
9. App calculates `resume_step: ALLERGIES`
10. App navigates to ALLERGIES screen (offline mode)

### Scenario 3: Server Temporarily Down
1. User has partially completed onboarding (last step: DIETARY)
2. Backend server crashes 🔥
3. User reopens app
4. Server call fails ❌
5. App reads local cache: `last_step: DIETARY`
6. App resumes from SPICE screen
7. User continues offline (skips optional steps)
8. User reaches COMPLETE screen
9. Completion API call fails ❌ (still offline)
10. Error shown: "Failed to complete onboarding"
11. User waits for server to recover
12. User retries → Success ✅

### Scenario 4: Multi-Device (Cache Isolation)
1. User completes HOUSEHOLD on Device A
2. Device A caches: `last_step: HOUSEHOLD, user_id: abc123`
3. User logs into Device B
4. Device B has no cache for user `abc123`
5. Device B calls server → gets `resume_step: ALLERGIES` ✅
6. Device B continues from ALLERGIES (correct)
7. User completes ALLERGIES on Device B
8. User returns to Device A (still cached at HOUSEHOLD)
9. Device A calls server → gets `resume_step: DIETARY` ✅
10. Server takes precedence (cache ignored if server reachable)

### Scenario 5: User Change (Cache Cleared)
1. User A completes HOUSEHOLD on device
2. Cache: `user_id: userA, last_step: HOUSEHOLD`
3. User A logs out
4. User B logs in (different account)
5. App checks cache: `getLastStep(userB)` → returns `null` (user mismatch)
6. Cache cleared for security ✅
7. User B starts from LOGIN (correct)

## Security Considerations

### User ID Validation
- Local cache **always** checks user ID before returning cached data
- Prevents cache pollution across users on shared devices
- Auto-clears cache when user mismatch detected

### Cache Tampering
- SharedPreferences stored in app sandbox (iOS Keychain/Android EncryptedSharedPreferences could be used for extra security)
- Server is **always** source of truth when reachable
- Local cache only used when server unreachable (temporary offline mode)
- Cache never overrides server data

### Privacy
- No sensitive data stored in cache (only step names and user ID)
- Profile data fetched from server on every app launch
- Cache cleared on logout

## Testing Guide

### Manual Testing

#### Test 1: Normal Online Resume
1. Complete HOUSEHOLD step
2. Close app
3. Reopen app (online)
4. **Expected**: Resumes at ALLERGIES (from server)
5. **Debug logs**: "Using server resume_step: ALLERGIES"

#### Test 2: Offline Resume with Cache
1. Complete HOUSEHOLD step (online)
2. Enable Airplane Mode 📴
3. Close app
4. Reopen app (offline)
5. **Expected**: Resumes at ALLERGIES (from cache)
6. **Debug logs**: "Using cached onboarding step: ALLERGIES (offline mode)"

#### Test 3: No Cache, No Server
1. Fresh install + login
2. Immediately enable Airplane Mode
3. Close app
4. Reopen app
5. **Expected**: Starts at LOGIN
6. **Debug logs**: "Error checking server" → "Ultimate fallback: LOGIN"

#### Test 4: Cache-Server Mismatch (Server Wins)
1. Complete HOUSEHOLD (cache: HOUSEHOLD)
2. Manually advance server to SPICE (via backend)
3. Reopen app (online)
4. **Expected**: Resumes at SPICE (server takes precedence)
5. **Verify**: Cache ignored when server reachable

#### Test 5: User Switch (Cache Cleared)
1. User A completes HOUSEHOLD
2. Log out User A
3. Log in User B
4. **Expected**: User B starts from LOGIN (cache doesn't apply)
5. **Debug logs**: "Cache user mismatch - cleared"

### Automated Testing (Unit Tests)

```dart
// Test OnboardingStorage methods
test('saveLastStep stores step with user ID', () async {
  await OnboardingStorage.saveLastStep('HOUSEHOLD', 'user123');
  final cached = await OnboardingStorage.getLastStep('user123');
  expect(cached, 'HOUSEHOLD');
});

test('getLastStep returns null for different user', () async {
  await OnboardingStorage.saveLastStep('HOUSEHOLD', 'user123');
  final cached = await OnboardingStorage.getLastStep('user456');
  expect(cached, null);
});

test('isOnboardingComplete returns true after COMPLETE', () async {
  await OnboardingStorage.saveLastStep('COMPLETE', 'user123');
  final isComplete = await OnboardingStorage.isOnboardingComplete('user123');
  expect(isComplete, true);
});

test('getResumeStep calculates next step correctly', () {
  expect(OnboardingStorage.getResumeStep('HOUSEHOLD'), 'ALLERGIES');
  expect(OnboardingStorage.getResumeStep('LANGUAGE'), 'COMPLETE');
  expect(OnboardingStorage.getResumeStep('COMPLETE'), 'COMPLETE');
});
```

### Integration Testing

```dart
// Test offline resume flow
testWidgets('App resumes from cached step when offline', (tester) async {
  // Setup: Complete HOUSEHOLD, cache step
  await OnboardingStorage.saveLastStep('HOUSEHOLD', 'testUser');
  
  // Mock server failure
  mockProfileService.when(() => getOnboardingStatus()).thenThrow(Exception('Offline'));
  
  // Act: Reopen app
  await tester.pumpWidget(SavoApp());
  await tester.pumpAndSettle();
  
  // Assert: Should show ALLERGIES screen (next after HOUSEHOLD)
  expect(find.byType(OnboardingAllergiesScreen), findsOneWidget);
});
```

## Performance Considerations

### Storage Size
- Minimal footprint: 3 SharedPreferences keys per user
- ~100 bytes total per cached user
- Negligible performance impact

### Read/Write Frequency
- **Write**: Once per onboarding step completion (~8 writes total per user)
- **Read**: Once on app launch
- No continuous polling or syncing

### Cache Expiry
- Cache has no TTL (time-to-live)
- Server always takes precedence when reachable
- Manual clear on logout

## Configuration

### No Additional Config Required
- Uses existing `shared_preferences` package (already in `pubspec.yaml`)
- No environment variables needed
- Works out-of-the-box with Phase E implementation

## Limitations

### Known Limitations

1. **Partial Step Data Not Cached**
   - Only completed step names cached
   - Form data within incomplete step not persisted locally
   - **Impact**: User must re-enter form data if app crashes mid-step

2. **No Conflict Resolution**
   - Server always wins (no merge strategy)
   - If server and cache disagree, server used
   - **Impact**: Cache only used when server unreachable

3. **Single Device Sync**
   - Cache per-device (not synced across devices)
   - Multi-device users rely on server sync
   - **Impact**: Acceptable (server is source of truth)

4. **No Offline Write Queue**
   - API writes require internet
   - Cannot complete steps while offline
   - **Impact**: User can navigate but not submit while offline

### Acceptable Trade-offs

✅ **Cache Staleness**: Acceptable because server always preferred  
✅ **No Conflict Resolution**: Not needed (server authoritative)  
✅ **Device-Specific Cache**: Acceptable (server syncs across devices)  

## Troubleshooting

### Issue: "Cache always returns null"
- **Cause**: User ID mismatch or cache never saved
- **Fix**: Check `debugPrint` logs for user ID consistency

### Issue: "App ignores cache even when offline"
- **Cause**: Session exists but server call succeeds (not truly offline)
- **Fix**: Verify Airplane Mode enabled, check server reachability

### Issue: "Resume step wrong after multi-device use"
- **Cause**: Cache on Device A outdated vs. server
- **Fix**: Expected behavior (server takes precedence when online)

## Success Criteria

✅ **All screens save progress locally**  
✅ **OnboardingCoordinator uses cache as fallback**  
✅ **AppStartupScreen uses cache as fallback**  
✅ **User ID validation prevents cross-user cache**  
✅ **Server always takes precedence when reachable**  
✅ **Offline resume works from any step**  
✅ **Cache cleared on user change**  
✅ **Completion status cached**  

**Phase F Status**: 🎉 **COMPLETE**

## Files Modified

### New Files
- `lib/services/onboarding_storage.dart` - Local storage service (114 lines)

### Modified Files
- `lib/main.dart` - AppStartupScreen with fallback logic
- `lib/screens/onboarding/onboarding_coordinator.dart` - Fallback in coordinator
- `lib/screens/onboarding/login_screen.dart` - Save LOGIN step (2 places)
- `lib/screens/onboarding/household_screen.dart` - Save HOUSEHOLD step
- `lib/screens/onboarding/allergies_screen.dart` - Save ALLERGIES step
- `lib/screens/onboarding/dietary_screen.dart` - Save DIETARY step
- `lib/screens/onboarding/spice_screen.dart` - Save SPICE step
- `lib/screens/onboarding/pantry_screen.dart` - Save PANTRY step
- `lib/screens/onboarding/language_screen.dart` - Save LANGUAGE step
- `lib/screens/onboarding/complete_screen.dart` - Save COMPLETE step

**Total Changes**: 1 new file + 11 modified files

## Next Steps

### Phase G: Allergen Editing Restrictions + Audit
- UI confirmation dialog for allergen removal
- Audit every profile write to `audit_log` table
- Display audit history to user

### Phase H: Multi-Device Session Management
- Active Sessions screen
- Sign out other devices
- Session metadata display

## Related Documentation

- [Phase E: Onboarding UI](./PHASE_E_COMPLETE.md)
- [Phase D: Flutter SDK](../docs/user_profile.md#phase-d)
- [user_profile.md](../user_profile.md) - Original specification
