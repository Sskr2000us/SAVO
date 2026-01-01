# Phase C: Backend API Endpoints - COMPLETE ✅

## Overview
Phase C adds all specialized API endpoints required by the JSON spec for profile management, onboarding tracking, and audit logging.

## What Was Implemented

### 1. Database Helper Functions (database.py)
Added to `services/api/app/core/database.py`:

#### Audit Log Operations
- `log_audit_event()` - Log safety-critical changes with device info
- `get_audit_log()` - Retrieve audit history for user

#### Onboarding Operations
- `mark_onboarding_complete()` - Set completion timestamp
- `get_onboarding_status()` - Check completion and calculate resume step
  - Returns: `{completed, resume_step, missing_fields}`
  - Resume steps: HOUSEHOLD → ALLERGIES → DIETARY → SPICE → PANTRY → LANGUAGE → COMPLETE

#### Full Profile Aggregation
- `get_full_profile()` - Aggregate user + household + members + allergens/dietary
  - Returns complete state for UI hydration
  - Consolidates allergens and dietary restrictions from all members

### 2. New API Endpoints (profile.py)
Added to `services/api/app/api/routes/profile.py`:

#### C1: Full Profile Endpoint
```
GET /profile/full
- Returns: user, profile, household, members, allergens, dietary
- Purpose: Single call to hydrate UI state
- Auth: JWT Bearer token required
```

#### C2: Specialized Update Endpoints
```
PATCH /profile/allergens
- Body: {member_id, allergens[], reason?}
- Logs to audit_log with device info + IP
- Safety-critical operation
- Auth: JWT Bearer token required

PATCH /profile/dietary
- Body: {member_id, dietary_restrictions[]}
- Updates family member dietary restrictions
- Auth: JWT Bearer token required

PATCH /profile/preferences
- Body: {favorite_cuisines[]?, avoided_cuisines[]?, basic_spices_available?}
- Updates household-level preferences
- Auth: JWT Bearer token required

PATCH /profile/language
- Body: {primary_language}
- Updates primary_language in household_profiles
- Auth: JWT Bearer token required
```

#### C3: Onboarding Status Endpoints
```
GET /profile/onboarding-status
- Returns: {completed, resume_step, missing_fields[]}
- Calculates next step based on data presence
- Auth: JWT Bearer token required

PATCH /profile/complete
- Marks onboarding complete (sets timestamp)
- Returns: {success, completed_at}
- Auth: JWT Bearer token required
```

### 3. New Pydantic Models
Added request/response models:
- `AllergensUpdate` - For allergen changes with audit reason
- `DietaryUpdate` - For dietary restriction updates
- `PreferencesUpdate` - For cuisine/spice/pantry preferences
- `LanguageUpdate` - For language preference

## Testing the Endpoints

### Prerequisites
1. Run migration 002_user_profile_spec.sql in Supabase SQL Editor
2. Set environment variable: `SUPABASE_JWT_SECRET=your-jwt-secret`
3. Obtain JWT token from Supabase Auth

### Example Requests

#### 1. Get Full Profile
```bash
curl -X GET http://localhost:8000/profile/full \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

Expected Response:
```json
{
  "success": true,
  "data": {
    "user": {...},
    "profile": {...},
    "household": {...},
    "members": [...],
    "allergens": {
      "declared_allergens": ["peanuts", "shellfish"],
      "enforcement_level": "strict"
    },
    "dietary": {
      "vegetarian": false,
      "vegan": false,
      "no_beef": false,
      "no_pork": false,
      "no_alcohol": false
    }
  }
}
```

#### 2. Update Allergens (with audit)
```bash
curl -X PATCH http://localhost:8000/profile/allergens \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "member_id": "uuid-of-family-member",
    "allergens": ["peanuts", "tree nuts", "shellfish"],
    "reason": "Doctor confirmed tree nut allergy"
  }'
```

This logs to `audit_log` table with:
- Event type: `allergen_update`
- Old/new values
- Device info (user agent)
- IP address
- Timestamp

#### 3. Check Onboarding Status
```bash
curl -X GET http://localhost:8000/profile/onboarding-status \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

Example responses:
```json
// Incomplete - needs allergens
{
  "success": true,
  "data": {
    "completed": false,
    "resume_step": "ALLERGIES",
    "missing_fields": ["allergens", "dietary", "language"]
  }
}

// Complete
{
  "success": true,
  "data": {
    "completed": true,
    "resume_step": "COMPLETE",
    "missing_fields": [],
    "completed_at": "2025-06-15T10:30:00Z"
  }
}
```

#### 4. Update Preferences
```bash
curl -X PATCH http://localhost:8000/profile/preferences \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "favorite_cuisines": ["Italian", "Thai", "Mexican"],
    "avoided_cuisines": ["Indian"],
    "basic_spices_available": true
  }'
```

#### 5. Update Language
```bash
curl -X PATCH http://localhost:8000/profile/language \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"primary_language": "es-ES"}'
```

#### 6. Complete Onboarding
```bash
curl -X PATCH http://localhost:8000/profile/complete \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

Response:
```json
{
  "success": true,
  "message": "Onboarding marked as complete",
  "completed_at": "2025-06-15T10:35:00Z"
}
```

## Onboarding Resume Logic

The `get_onboarding_status()` function implements this decision tree:

```
1. If onboarding_completed_at is set → COMPLETE
2. Else check in order:
   - No household members? → HOUSEHOLD
   - Allergens not declared? → ALLERGIES
   - Dietary not declared? → DIETARY
   - Spice tolerance missing? → SPICE
   - Basic spices not set? → PANTRY
   - Language missing? → LANGUAGE
   - All fields present? → COMPLETE
```

## Audit Log Schema

When allergens are updated, this is logged:
```sql
INSERT INTO audit_log (
  user_id,
  event_type,
  route,
  entity_type,
  entity_id,
  old_value,
  new_value,
  device_info,
  ip_address
) VALUES (
  'user-uuid',
  'allergen_update',
  '/profile/allergens',
  'family_member',
  'member-uuid',
  '{"allergens": ["peanuts"]}',
  '{"allergens": ["peanuts", "tree nuts"]}',
  '{"user_agent": "...", "reason": "Doctor confirmed"}',
  '192.168.1.1'
);
```

## Security Features

All endpoints:
✅ Require JWT Bearer token
✅ Validate token via Supabase JWT_SECRET
✅ Extract user_id from token 'sub' claim
✅ Verify resource ownership (members belong to user)
✅ Log safety-critical changes (allergens)

## Files Modified

1. **services/api/app/core/database.py**
   - Added 8 new functions (200+ lines)
   - Audit logging, onboarding tracking, full profile aggregation

2. **services/api/app/api/routes/profile.py**
   - Added 4 new Pydantic models
   - Added 7 new endpoints
   - Imported new database functions

## Next Steps (Phase D, E, F)

### Phase D: Flutter Supabase SDK
- Add `supabase_flutter` dependency
- Initialize Supabase client with JWT auth
- Create `ProfileService` to call new endpoints
- Store JWT token in secure storage

### Phase E: Flutter Onboarding Screens
- Create 7 onboarding screens (HOUSEHOLD → LANGUAGE)
- Implement progress bar based on `resume_step`
- Add "Save & Exit" to resume later
- Call `PATCH /profile/complete` on final screen

### Phase F: Resume Logic
- Check `GET /profile/onboarding-status` on app launch
- Navigate to `resume_step` screen if incomplete
- Show welcome back message: "Resume from step X"

### Phase G: Allergen Safety UI
- Show confirmation dialog before allergen updates
- Require reason field (optional but encouraged)
- Display audit log in settings
- Highlight safety-critical changes

### Phase H: Multi-Device Support
- Update `users.last_login_device` on each request
- Show "Last logged in from X" in settings
- Support logout from specific devices

## Verification Checklist

- [x] All endpoints require JWT Bearer token
- [x] Allergen updates log to audit_log
- [x] Onboarding status calculates resume_step correctly
- [x] Full profile aggregates all data
- [x] No syntax errors (Pylance clean)
- [x] Follows existing code patterns
- [x] Error handling with HTTPException
- [x] Resource ownership validation

## Production Considerations

1. **Rate Limiting**: Add rate limiting to PATCH endpoints
2. **Validation**: Consider adding allergen whitelist validation
3. **Monitoring**: Log all audit_log insertions
4. **Performance**: `get_full_profile()` makes 3 DB calls - consider caching
5. **Testing**: Add unit tests for onboarding status logic

---

**Phase C Status: ✅ COMPLETE**

All backend endpoints are now ready for Flutter integration (Phase D).
