# API Endpoint Reference - Profile System

## Base URL
```
http://localhost:8000
```

## Authentication
All endpoints require JWT Bearer token:
```
Authorization: Bearer YOUR_SUPABASE_JWT_TOKEN
```

---

## Existing Endpoints (Refactored to JWT)

### GET /profile/household
Get household profile for authenticated user.

**Response:**
```json
{
  "exists": true,
  "profile": {
    "id": "uuid",
    "user_id": "uuid",
    "region": "US",
    "culture": "western",
    "primary_language": "en-US",
    "favorite_cuisines": ["Italian", "Mexican"],
    "avoided_cuisines": [],
    "skill_level": 2,
    ...
  }
}
```

### POST /profile/household
Create household profile (one-time setup).

**Request:**
```json
{
  "region": "US",
  "culture": "western",
  "primary_language": "en-US",
  "measurement_system": "imperial",
  "favorite_cuisines": ["Italian", "Mexican"],
  "skill_level": 2
}
```

### PATCH /profile/household
Update household profile.

**Request:**
```json
{
  "favorite_cuisines": ["Italian", "Thai"],
  "skill_level": 3
}
```

### GET /profile/family-members
Get all family members.

**Response:**
```json
{
  "members": [
    {
      "id": "uuid",
      "name": "John",
      "age": 35,
      "allergens": ["peanuts"],
      "dietary_restrictions": ["vegetarian"],
      "spice_tolerance": "medium"
    }
  ]
}
```

### POST /profile/family-members
Create family member.

**Request:**
```json
{
  "name": "Alice",
  "age": 8,
  "allergens": ["shellfish"],
  "dietary_restrictions": [],
  "spice_tolerance": "mild"
}
```

### PATCH /profile/family-members/{member_id}
Update family member.

**Request:**
```json
{
  "age": 9,
  "spice_tolerance": "medium"
}
```

### DELETE /profile/family-members/{member_id}
Remove family member.

---

## New Endpoints (Phase C)

### GET /profile/full
Get complete user profile with all related data.

**Response:**
```json
{
  "success": true,
  "data": {
    "user": {
      "id": "uuid",
      "email": "user@example.com",
      "created_at": "2025-01-15T10:00:00Z",
      "last_login_device": "iPhone 13"
    },
    "profile": {
      "id": "uuid",
      "user_id": "uuid",
      "region": "US",
      "primary_language": "en-US",
      "favorite_cuisines": ["Italian", "Mexican"],
      "basic_spices_available": true,
      "onboarding_completed_at": "2025-01-15T10:30:00Z"
    },
    "household": {
      // Same as profile
    },
    "members": [
      {
        "id": "uuid",
        "name": "John",
        "age": 35,
        "allergens": ["peanuts"],
        "dietary_restrictions": ["vegetarian"]
      }
    ],
    "allergens": {
      "declared_allergens": ["peanuts", "shellfish"],
      "enforcement_level": "strict"
    },
    "dietary": {
      "vegetarian": true,
      "vegan": false,
      "no_beef": false,
      "no_pork": false,
      "no_alcohol": false
    }
  }
}
```

---

### PATCH /profile/allergens
Update allergens for a family member (with audit logging).

**Request:**
```json
{
  "member_id": "uuid",
  "allergens": ["peanuts", "tree nuts", "shellfish"],
  "reason": "Doctor confirmed tree nut allergy"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Allergens updated successfully",
  "member": {
    "id": "uuid",
    "name": "Alice",
    "allergens": ["peanuts", "tree nuts", "shellfish"]
  }
}
```

**Audit Log Entry:**
```json
{
  "user_id": "uuid",
  "event_type": "allergen_update",
  "route": "/profile/allergens",
  "entity_type": "family_member",
  "entity_id": "member-uuid",
  "old_value": {"allergens": ["peanuts"]},
  "new_value": {"allergens": ["peanuts", "tree nuts", "shellfish"]},
  "device_info": {
    "user_agent": "Mozilla/5.0...",
    "reason": "Doctor confirmed tree nut allergy"
  },
  "ip_address": "192.168.1.1",
  "created_at": "2025-06-15T10:30:00Z"
}
```

---

### PATCH /profile/dietary
Update dietary restrictions for a family member.

**Request:**
```json
{
  "member_id": "uuid",
  "dietary_restrictions": ["vegetarian", "no_alcohol"]
}
```

**Response:**
```json
{
  "success": true,
  "message": "Dietary restrictions updated successfully",
  "member": {
    "id": "uuid",
    "name": "John",
    "dietary_restrictions": ["vegetarian", "no_alcohol"]
  }
}
```

---

### PATCH /profile/preferences
Update household preferences.

**Request:**
```json
{
  "favorite_cuisines": ["Italian", "Thai", "Mexican"],
  "avoided_cuisines": ["Indian"],
  "basic_spices_available": true
}
```

**Response:**
```json
{
  "success": true,
  "message": "Preferences updated successfully",
  "profile": {
    "id": "uuid",
    "favorite_cuisines": ["Italian", "Thai", "Mexican"],
    "avoided_cuisines": ["Indian"],
    "basic_spices_available": true
  }
}
```

---

### PATCH /profile/language
Update primary language for household.

**Request:**
```json
{
  "primary_language": "es-ES"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Language updated successfully",
  "profile": {
    "id": "uuid",
    "primary_language": "es-ES"
  }
}
```

---

### GET /profile/onboarding-status
Get onboarding completion status and resume step.

**Response (Incomplete):**
```json
{
  "success": true,
  "data": {
    "completed": false,
    "resume_step": "ALLERGIES",
    "missing_fields": ["allergens", "dietary", "language"]
  }
}
```

**Response (Complete):**
```json
{
  "success": true,
  "data": {
    "completed": true,
    "resume_step": "COMPLETE",
    "missing_fields": [],
    "completed_at": "2025-01-15T10:30:00Z"
  }
}
```

**Resume Step Flow:**
```
HOUSEHOLD → ALLERGIES → DIETARY → SPICE → PANTRY → LANGUAGE → COMPLETE
```

---

### PATCH /profile/complete
Mark onboarding as completed.

**Request:** (No body required)

**Response:**
```json
{
  "success": true,
  "message": "Onboarding marked as complete",
  "completed_at": "2025-06-15T10:35:00Z"
}
```

This sets `household_profiles.onboarding_completed_at` timestamp.

---

## Error Responses

### 401 Unauthorized
```json
{
  "detail": "Invalid or expired token"
}
```

### 404 Not Found
```json
{
  "detail": "Family member not found or access denied"
}
```

### 400 Bad Request
```json
{
  "detail": "No valid fields provided for update"
}
```

### 500 Internal Server Error
```json
{
  "detail": "Database error message"
}
```

---

## Testing with curl

### 1. Get JWT Token from Supabase
```javascript
// In browser console on your Supabase app
const { data, error } = await supabase.auth.signInWithPassword({
  email: 'test@example.com',
  password: 'password123'
});
console.log(data.session.access_token);
```

### 2. Export Token
```bash
export JWT_TOKEN="your-jwt-token-here"
```

### 3. Test Endpoints
```bash
# Get full profile
curl -X GET http://localhost:8000/profile/full \
  -H "Authorization: Bearer $JWT_TOKEN"

# Update allergens
curl -X PATCH http://localhost:8000/profile/allergens \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "member_id": "member-uuid",
    "allergens": ["peanuts", "shellfish"],
    "reason": "Test update"
  }'

# Check onboarding status
curl -X GET http://localhost:8000/profile/onboarding-status \
  -H "Authorization: Bearer $JWT_TOKEN"

# Complete onboarding
curl -X PATCH http://localhost:8000/profile/complete \
  -H "Authorization: Bearer $JWT_TOKEN"
```

---

## Database Tables

### users
```sql
id (uuid), email (text), created_at (timestamptz), last_login_device (text)
```

### household_profiles
```sql
id (uuid), user_id (uuid), region, culture, primary_language,
favorite_cuisines (text[]), avoided_cuisines (text[]),
basic_spices_available (boolean), onboarding_completed_at (timestamptz)
```

### family_members
```sql
id (uuid), household_profile_id (uuid), name, age,
allergens (text[]), dietary_restrictions (text[]),
spice_tolerance (text)
```

### audit_log
```sql
id (uuid), user_id (uuid), event_type, route, entity_type, entity_id,
old_value (jsonb), new_value (jsonb), device_info (jsonb),
ip_address (inet), created_at (timestamptz)
```

---

## Quick Start Workflow

1. **Login** → Get JWT token from Supabase Auth
2. **Create Household** → `POST /profile/household`
3. **Add Members** → `POST /profile/family-members`
4. **Set Allergens** → `PATCH /profile/allergens` (audited)
5. **Set Dietary** → `PATCH /profile/dietary`
6. **Set Preferences** → `PATCH /profile/preferences`
7. **Set Language** → `PATCH /profile/language`
8. **Complete Onboarding** → `PATCH /profile/complete`
9. **Get Full Profile** → `GET /profile/full`

At any point, check progress with `GET /profile/onboarding-status`.
