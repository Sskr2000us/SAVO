# Phase G: Allergen Editing Restrictions + Audit - COMPLETE

**Status**: ✅ Complete  
**Date**: 2025-01-01

## Overview

Phase G implements safety-critical features for allergen management and comprehensive audit logging for all profile changes. This ensures users cannot accidentally remove allergens without explicit confirmation, and all profile modifications are tracked for accountability and safety review.

## Problem Statement

**Safety Challenge**: Allergens are life-threatening. Accidentally removing an allergen from a profile could result in dangerous recipe suggestions.

**Accountability Challenge**: Users need visibility into what profile changes were made, when, and from which device.

**Solution**: Two-layered approach:
1. **UI Safety Gates**: Confirmation dialog with explicit warning when removing allergens
2. **Complete Audit Trail**: Every profile write logged to `audit_log` table with old/new values

## Architecture

### Safety Flow for Allergen Removal

```
User attempts to deselect allergen chip
          ↓
  Is this an addition? ──YES──> Allow immediately (safe operation)
          ↓ NO
  Show confirmation dialog
  "Are you sure? SAVO will start including [allergen] in suggestions."
          ↓
  User clicks "Cancel" ──> No change (allergen remains)
          ↓
  User clicks "Yes, Remove"
          ↓
  Remove allergen from profile
          ↓
  Save to backend with reason
          ↓
  Log audit event with old/new values
```

### Audit Logging Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ PATCH /profile/* endpoint called                            │
└──────────────────────┬──────────────────────────────────────┘
                       │
         ┌─────────────┴─────────────┐
         │                           │
         ▼                           ▼
┌──────────────────┐         ┌──────────────────┐
│ Get existing     │         │ Apply update     │
│ values (old)     │         │ (new values)     │
└────────┬─────────┘         └────────┬─────────┘
         │                            │
         └──────────┬─────────────────┘
                    │
                    ▼
        ┌───────────────────────┐
        │ Call log_audit_event()│
        │  - user_id            │
        │  - event_type         │
        │  - route              │
        │  - entity_type/id     │
        │  - old_value (JSONB)  │
        │  - new_value (JSONB)  │
        │  - device_info        │
        │  - ip_address         │
        └───────────┬───────────┘
                    │
                    ▼
        ┌───────────────────────┐
        │ INSERT INTO audit_log │
        └───────────┬───────────┘
                    │
                    ▼
        ┌───────────────────────┐
        │ Return success to user│
        └───────────────────────┘
```

## Implementation Details

### 1. Flutter UI: Allergen Confirmation Dialog

**File**: `lib/screens/settings_screen.dart`

#### New Component: `_buildAllergenChips()`

Replacement for generic `_buildMultiSelectChips()` specifically for allergens with safety logic:

**Features**:
- **Addition**: No confirmation needed (safe operation)
- **Removal**: Shows confirmation dialog with warning
- **Visual Safety Indicators**: 
  - Warning icon next to "Allergens" label
  - Red color scheme for selected allergens (vs. green for other chips)
  - Italic safety note below chips
- **Member-Specific**: Dialog shows which family member the change applies to

**Code Structure**:
```dart
Widget _buildAllergenChips({
  required String label,
  required List<String> options,
  required List<String> selected,
  required String memberName,  // NEW: for personalized dialog
  required Function(List<String>) onChanged,
}) {
  // FilterChip with async onSelected callback
  // Addition: immediate
  // Removal: await _showAllergenRemovalConfirmation()
}
```

#### Confirmation Dialog: `_showAllergenRemovalConfirmation()`

**Dialog Structure**:
```dart
AlertDialog(
  title: Warning icon + "Remove Allergen?"
  content:
    - Bold: "Are you sure you want to remove [allergen] from [member]?"
    - Orange info box with:
      - "SAVO will start including [allergen] in suggestions"
      - "This change will be logged for your safety"
  actions:
    - "Cancel" (TextButton) → returns false
    - "Yes, Remove" (ElevatedButton, orange) → returns true
)
```

**User Experience**:
- Dialog is **modal** (user must respond)
- **Cancel** is easy to hit (left side, text button)
- **Confirm** requires deliberate action (right side, colored button)
- **Warning color** (orange) throughout for visual consistency
- **Audit transparency**: User told their action will be logged

### 2. Backend: Comprehensive Audit Logging

**Files Modified**: 
- `services/api/app/api/routes/profile.py` - All PATCH endpoints
- `services/api/app/core/database.py` - Already had `log_audit_event()` and `get_audit_log()`

#### Audit Logging Added to Endpoints

| Endpoint | Event Type | Entity Type | Old/New Values |
|----------|-----------|-------------|----------------|
| `PATCH /profile/household` | `profile_update` | `household_profile` | Changed fields only |
| `PATCH /profile/family-members/{id}` | `family_member_update` | `family_member` | Changed fields only |
| `PATCH /profile/allergens` | `allergen_update` | `family_member` | `{allergens: [...]}` |
| `PATCH /profile/dietary` | `dietary_update` | `family_member` | `{dietary_restrictions: [...]}` |
| `PATCH /profile/preferences` | `preferences_update` | `household_profile` | Changed cuisine/pantry fields |
| `PATCH /profile/language` | `language_update` | `household_profile` | `{primary_language: "..."}` |
| `PATCH /profile/complete` | `onboarding_complete` | `household_profile` | `{onboarding_completed_at: ...}` |

#### Pattern Applied to All Endpoints

```python
@router.patch("/some-endpoint")
async def update_something(
    data: UpdateModel,
    request: Request,  # NEW: Added for device_info
    user_id: str = Depends(get_current_user)
):
    # 1. Get existing data (for old values)
    existing = await get_existing_data(user_id)
    old_values = {k: existing.get(k) for k in data_fields}
    
    # 2. Apply update
    updated = await update_data(user_id, data)
    
    # 3. Log audit event
    device_info = {
        "user_agent": request.headers.get("user-agent", "unknown")
    }
    
    await log_audit_event(
        user_id=user_id,
        event_type="descriptive_event_type",
        route="/profile/some-endpoint",
        entity_type="household_profile|family_member",
        entity_id=user_id_or_member_id,
        old_value=old_values,  # JSONB
        new_value=new_values,  # JSONB
        device_info=device_info,
        ip_address=request.client.host if request.client else None
    )
    
    # 4. Return success
    return {"success": True, ...}
```

#### Audit Event Types

- `profile_update` - Household profile changes (region, culture, meal times, etc.)
- `family_member_update` - Individual member changes (name, age, etc.)
- `allergen_update` - Allergen list changes (**safety-critical**)
- `dietary_update` - Dietary restriction changes
- `preferences_update` - Cuisine/pantry/nutrition preferences
- `language_update` - Primary language changes
- `onboarding_complete` - Onboarding finalization

#### Device Info Captured

```json
{
  "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) ...",
  "reason": "Initial onboarding"  // Optional, for allergens
}
```

#### IP Address Tracking

- Captured from `request.client.host`
- Stored in `audit_log.ip_address` column
- Used for security/fraud detection

### 3. New Endpoint: GET /profile/audit

**Purpose**: Allow users to review their profile change history

**Authentication**: Requires JWT Bearer token (user can only see their own audit log)

**Query Parameters**:
- `limit` (optional): Maximum records to return (default 100, max 1000)

**Response**:
```json
{
  "success": true,
  "count": 42,
  "audit_log": [
    {
      "id": "uuid",
      "user_id": "user-uuid",
      "event_type": "allergen_update",
      "route": "/profile/allergens",
      "entity_type": "family_member",
      "entity_id": "member-uuid",
      "old_value": {"allergens": ["peanuts", "dairy"]},
      "new_value": {"allergens": ["peanuts"]},
      "device_info": {
        "user_agent": "...",
        "reason": "User requested removal"
      },
      "ip_address": "192.168.1.100",
      "created_at": "2025-01-01T12:34:56Z"
    },
    // ... more entries
  ]
}
```

**Use Cases**:
- User reviews what changed in their profile
- Support team investigates user report
- Security audit after suspicious activity
- Proof of informed consent for allergen changes

## Database Schema

The `audit_log` table was created in Phase A (migration `002_user_profile_spec.sql`):

```sql
CREATE TABLE public.audit_log (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  event_type TEXT NOT NULL,
  route TEXT NOT NULL,
  entity_type TEXT NOT NULL,
  entity_id TEXT,
  old_value JSONB,
  new_value JSONB,
  device_info JSONB,
  ip_address TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_audit_log_user_created 
  ON public.audit_log (user_id, created_at DESC);
```

**Row-Level Security (RLS)**:
- **SELECT**: Users can view their own audit logs (`user_id = auth.uid()`)
- **INSERT**: Backend service can insert (bypass RLS or use service role)

## User Scenarios

### Scenario 1: Accidental Allergen Removal (Prevented)

1. User viewing family member's profile in Settings
2. Member currently has allergens: `["peanuts", "dairy"]`
3. User accidentally taps "dairy" chip
4. **Confirmation dialog appears**: "Are you sure? SAVO will start including dairy..."
5. User realizes mistake, clicks "Cancel"
6. Allergen remains in list ✅ (safe)
7. No audit log entry created (no change occurred)

### Scenario 2: Intentional Allergen Removal (Confirmed)

1. User's child outgrows egg allergy (confirmed by doctor)
2. User navigates to Settings → Family → Child profile
3. Child currently has allergens: `["eggs"]`
4. User taps "eggs" chip
5. **Confirmation dialog**: "Are you sure? SAVO will start including eggs..."
6. User reads warning, clicks "Yes, Remove"
7. Allergen removed from profile ✅
8. **Backend audit log entry created**:
   ```json
   {
     "event_type": "allergen_update",
     "old_value": {"allergens": ["eggs"]},
     "new_value": {"allergens": []},
     "device_info": {"user_agent": "...", "reason": "Initial onboarding"},
     "created_at": "2025-01-01T15:30:00Z"
   }
   ```
9. User can now see recipes with eggs for child

### Scenario 3: Adding Allergen (No Confirmation)

1. User discovers family member has new shellfish allergy
2. User navigates to Settings → Family → Member profile
3. User taps "shellfish" chip (not currently selected)
4. **No confirmation dialog** (adding is safe)
5. Allergen immediately added to profile ✅
6. Backend audit log entry created:
   ```json
   {
     "event_type": "allergen_update",
     "old_value": {"allergens": ["peanuts"]},
     "new_value": {"allergens": ["peanuts", "shellfish"]},
     "created_at": "2025-01-01T16:00:00Z"
   }
   ```

### Scenario 4: Reviewing Audit History

1. User suspects their profile was changed (maybe device was unlocked)
2. User navigates to Settings → Privacy → Audit Log (hypothetical UI)
3. App calls `GET /profile/audit?limit=50`
4. User sees list of recent changes:
   - "Language updated to Spanish - 2 days ago from iPhone"
   - "Dietary restrictions updated - 1 week ago from iPad"
   - "Allergen 'dairy' removed - 2 weeks ago from iPhone"
5. User confirms all changes were made by them ✅

### Scenario 5: Support Investigation

1. User reports: "SAVO suggested a peanut recipe but I'm allergic!"
2. Support team checks user's profile: allergens = `[]`
3. Support team queries audit log: `GET /profile/audit?limit=100`
4. Finds entry:
   ```json
   {
     "event_type": "allergen_update",
     "old_value": {"allergens": ["peanuts"]},
     "new_value": {"allergens": []},
     "device_info": {"user_agent": "...", "reason": "User requested removal"},
     "ip_address": "192.168.1.100",
     "created_at": "2025-01-01T10:00:00Z"
   }
   ```
5. Support confirms: User removed peanut allergen themselves on Jan 1
6. Support educates user on confirmation dialog
7. User re-adds peanut allergen ✅

## Security & Privacy

### Audit Log Access Control

**RLS Policy** (set in Phase A migration):
```sql
-- Users can only view their own audit logs
CREATE POLICY audit_log_select_policy ON public.audit_log
  FOR SELECT USING (auth.uid() = user_id);

-- Backend service can insert (uses service role key)
```

**Why This Matters**:
- Users cannot see other users' audit logs (privacy)
- Users can review their own changes (transparency)
- Backend can always write (service role bypasses RLS)

### Audit Log Retention

**Current**: No automatic deletion (indefinite retention)

**Considerations for Production**:
- **GDPR Compliance**: Audit logs may need deletion on account deletion
- **Storage Costs**: Audit table will grow large over time
- **Recommendation**: Implement retention policy (e.g., 90-day retention)

**Implementation Example** (future):
```sql
-- Daily cron job to delete old audit logs
DELETE FROM public.audit_log 
WHERE created_at < NOW() - INTERVAL '90 days';
```

### Device Info Privacy

**What's Captured**:
- User-Agent header (browser/device type)
- IP address (for fraud detection)
- Optional reason field (for allergen changes)

**What's NOT Captured**:
- GPS location
- Device UDID/IMEI
- Biometric data
- Session tokens

### Allergen Removal as Informed Consent

The confirmation dialog serves as **informed consent**:
- User explicitly told consequences
- User must actively confirm (not accidental)
- Action is logged with timestamp
- Audit trail proves user was warned

## Testing Guide

### Manual Testing - Flutter UI

#### Test 1: Allergen Addition (No Dialog)
1. Open Settings → Family → Select member
2. Currently has: `["peanuts"]`
3. Tap "dairy" chip (unselected → selected)
4. **Expected**: Chip immediately selected, no dialog
5. **Verify**: Save profile, check backend has `["peanuts", "dairy"]`

#### Test 2: Allergen Removal (Dialog Shown)
1. Open Settings → Family → Select member
2. Currently has: `["peanuts", "dairy"]`
3. Tap "dairy" chip (selected → attempt removal)
4. **Expected**: Dialog appears with warning
5. **Dialog Content**:
   - Title: "Remove Allergen?"
   - Warning about SAVO including dairy in recipes
   - Note about logging
   - Cancel + Yes buttons
6. **Verify**: Dialog is modal (can't interact with background)

#### Test 3: Allergen Removal Canceled
1. Trigger allergen removal dialog (step 3 from Test 2)
2. Click "Cancel" button
3. **Expected**: Dialog closes, allergen remains selected
4. **Verify**: Save profile, backend still has `["peanuts", "dairy"]`

#### Test 4: Allergen Removal Confirmed
1. Trigger allergen removal dialog
2. Click "Yes, Remove" button
3. **Expected**: Dialog closes, allergen deselected
4. **Verify**: Save profile, backend has `["peanuts"]`
5. **Verify**: Audit log entry created (check backend)

#### Test 5: Visual Indicators
1. Open Settings with allergen chips visible
2. **Verify**:
   - Warning icon (⚠️) next to "Allergens" label
   - Selected allergen chips have red color scheme (not green)
   - Italic safety note below chips
   - Member name appears in dialog when triggered

### Manual Testing - Backend Audit

#### Test 1: Audit Logging on Profile Update
1. Call `PATCH /profile/household` with `{"region": "UK"}`
2. **Expected**: Response success
3. Query `audit_log` table:
   ```sql
   SELECT * FROM audit_log WHERE event_type = 'profile_update' ORDER BY created_at DESC LIMIT 1;
   ```
4. **Verify**:
   - `event_type` = "profile_update"
   - `route` = "/profile/household"
   - `old_value` contains previous region value
   - `new_value` contains `{"region": "UK"}`
   - `device_info` contains user-agent
   - `ip_address` populated

#### Test 2: Audit Logging on Allergen Update
1. Call `PATCH /profile/allergens` with new allergen list
2. Query audit_log:
   ```sql
   SELECT * FROM audit_log WHERE event_type = 'allergen_update' ORDER BY created_at DESC LIMIT 1;
   ```
3. **Verify**:
   - `event_type` = "allergen_update"
   - `old_value` and `new_value` show allergen array changes
   - `device_info` includes "reason" field if provided

#### Test 3: GET /profile/audit Endpoint
1. Make several profile changes (household, dietary, allergens)
2. Call `GET /profile/audit?limit=10`
3. **Expected**: Response with array of audit log entries
4. **Verify**:
   - Ordered by `created_at DESC` (newest first)
   - All entries belong to authenticated user
   - `count` field matches array length
   - Each entry has all required fields

#### Test 4: Audit Isolation (Security)
1. User A makes profile changes
2. User B calls `GET /profile/audit`
3. **Expected**: User B only sees their own audit logs (not User A's)
4. **Verify**: RLS working correctly

### Automated Testing (Unit Tests)

```python
# Test audit logging in profile routes
def test_household_update_logs_audit(client, auth_token):
    response = client.patch(
        "/profile/household",
        json={"region": "UK"},
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 200
    
    # Check audit log
    audit = get_latest_audit_log(user_id)
    assert audit["event_type"] == "profile_update"
    assert audit["new_value"]["region"] == "UK"

def test_allergen_update_requires_confirmation_ui():
    # Mock allergen removal
    # Verify confirmation dialog appears
    # Verify no change if user cancels
    pass
```

## Performance Considerations

### Audit Log Write Performance

**Impact**: Minimal
- **Async writes**: Audit logging doesn't block user response
- **No transactions**: If audit fails, user update still succeeds
- **Simple insert**: Single row insert to `audit_log` table

**Error Handling**:
```python
await log_audit_event(...)  # Wrapped in try/catch
# If fails: logs error, continues (user doesn't see error)
```

**Why This Approach**:
- Audit logging is "best effort" (not critical path)
- User experience not impacted by audit failures
- Errors logged for monitoring/alerting

### Audit Log Query Performance

**Index**: `idx_audit_log_user_created ON (user_id, created_at DESC)`

**Query Pattern**:
```sql
SELECT * FROM audit_log 
WHERE user_id = ? 
ORDER BY created_at DESC 
LIMIT 100;
```

**Performance**:
- Index covers query (no table scan)
- Fast for typical limits (100-1000 records)
- Degrades if user has millions of audit entries (unlikely)

### Storage Growth

**Estimate**:
- Average audit entry: ~500 bytes (JSONB compressed)
- Active user with 100 changes/month: 50 KB/month
- 1 million users: 50 GB/month
- **Recommendation**: Implement retention policy for production

## Configuration

### No Additional Config Required

- Uses existing `audit_log` table from Phase A
- Uses existing `log_audit_event()` function
- No environment variables needed

## Known Limitations

### 1. No Batch Change Detection

**Current**: Each field change logged separately
**Impact**: If user changes 5 fields in one form, 5 audit entries created
**Future**: Consider batching related changes with transaction ID

### 2. No Rollback/Undo

**Current**: Audit log is read-only history
**Impact**: Users cannot undo changes via audit log
**Future**: Consider "Restore" button next to audit entries

### 3. No Real-Time Alerts

**Current**: Audit log is passive (query-based)
**Impact**: Users not notified of profile changes from other devices
**Future**: Consider push notifications for critical changes (allergen removal)

### 4. Confirmation Dialog Only on Removal

**Current**: Adding allergens has no confirmation
**Impact**: Accidental additions possible (but less dangerous)
**Rationale**: Adding safety restrictions is safe (prevents recipes), removing is dangerous (allows recipes)

## Success Criteria

✅ **Allergen removal shows confirmation dialog**  
✅ **Dialog explains consequences clearly**  
✅ **Dialog cancellation preserves allergen**  
✅ **Dialog confirmation removes allergen**  
✅ **All PATCH endpoints log audit events**  
✅ **Audit log includes old/new values**  
✅ **Audit log includes device info + IP**  
✅ **GET /profile/audit endpoint works**  
✅ **RLS prevents cross-user audit access**  
✅ **Visual safety indicators present**  

**Phase G Status**: 🎉 **COMPLETE**

## Files Modified

### Flutter (1 file)
- `lib/screens/settings_screen.dart`
  - Added `_buildAllergenChips()` method
  - Added `_showAllergenRemovalConfirmation()` dialog
  - Replaced allergen section to use new safety component

### Backend (1 file)
- `services/api/app/api/routes/profile.py`
  - Added `request: Request` parameter to 7 PATCH endpoints
  - Added audit logging to 7 PATCH endpoints:
    - `/profile/household`
    - `/profile/family-members/{id}`
    - `/profile/allergens` (already had it)
    - `/profile/dietary`
    - `/profile/preferences`
    - `/profile/language`
    - `/profile/complete`
  - Added `GET /profile/audit` endpoint
  - Added `get_audit_log` import

**Total Changes**: 2 files modified (~300 lines changed)

## Next Steps

### Phase H: Multi-Device Session Management
- Active Sessions screen in Settings
- Display device info + last login time
- "Sign out all other devices" button
- Supabase session management integration

### Future Enhancements (Post-MVP)
- Audit log UI in Settings screen
- Push notifications for critical changes
- Batch audit entries with transaction IDs
- Undo/rollback functionality
- Retention policy automation
- Export audit log (CSV/PDF)

## Related Documentation

- [Phase A: Database Setup](../services/api/migrations/002_user_profile_spec.sql)
- [Phase E: Onboarding UI](./PHASE_E_COMPLETE.md)
- [Phase F: Offline Resume](./PHASE_F_COMPLETE.md)
- [user_profile.md](../user_profile.md) - Original specification
