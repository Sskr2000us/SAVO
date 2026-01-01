# User Profile System - Architecture Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                        FLUTTER MOBILE APP                        │
│                         (Phase D, E, F)                          │
└──────────────────┬──────────────────────────────────────────────┘
                   │ JWT Bearer Token
                   ▼
┌─────────────────────────────────────────────────────────────────┐
│                     FASTAPI BACKEND (RENDER)                     │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │              JWT Middleware (Phase B)                       │ │
│ │  ┌──────────────────────────────────────────────────────┐   │ │
│ │  │ get_current_user()                                   │   │ │
│ │  │ - Validates JWT token                                │   │ │
│ │  │ - Extracts user_id from 'sub' claim                  │   │ │
│ │  │ - Returns user_id or raises 401                      │   │ │
│ │  └──────────────────────────────────────────────────────┘   │ │
│ └─────────────────────────────────────────────────────────────┘ │
│                   ▼                                               │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │           Profile Routes (Phases B & C)                     │ │
│ │                                                             │ │
│ │  EXISTING (Refactored):                                     │ │
│ │  ├─ GET    /profile/household                              │ │
│ │  ├─ POST   /profile/household                              │ │
│ │  ├─ PATCH  /profile/household                              │ │
│ │  ├─ GET    /profile/family-members                         │ │
│ │  ├─ POST   /profile/family-members                         │ │
│ │  ├─ PATCH  /profile/family-members/{id}                    │ │
│ │  └─ DELETE /profile/family-members/{id}                    │ │
│ │                                                             │ │
│ │  NEW (Phase C):                                             │ │
│ │  ├─ GET   /profile/full ──────────────┐                    │ │
│ │  ├─ PATCH /profile/allergens ─────────┤ (with audit)       │ │
│ │  ├─ PATCH /profile/dietary            │                    │ │
│ │  ├─ PATCH /profile/preferences        │                    │ │
│ │  ├─ PATCH /profile/language           │                    │ │
│ │  ├─ GET   /profile/onboarding-status  │                    │ │
│ │  └─ PATCH /profile/complete           │                    │ │
│ └───────────────────────────┬───────────┴───────────────────┘ │
│                             ▼                                   │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │              Database Functions (Phase C)                   │ │
│ │                                                             │ │
│ │  Audit Log:                                                 │ │
│ │  ├─ log_audit_event()                                       │ │
│ │  └─ get_audit_log()                                         │ │
│ │                                                             │ │
│ │  Onboarding:                                                │ │
│ │  ├─ mark_onboarding_complete()                              │ │
│ │  └─ get_onboarding_status()                                 │ │
│ │     Returns: {completed, resume_step, missing_fields}       │ │
│ │                                                             │ │
│ │  Aggregation:                                               │ │
│ │  └─ get_full_profile()                                      │ │
│ │     Returns: user + household + members + allergens         │ │
│ └───────────────────────────┬───────────────────────────────┘ │
└─────────────────────────────┼───────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   SUPABASE POSTGRESQL                            │
│                      (Phase A)                                   │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │  users                                                       │ │
│ │  ├─ id (uuid, pk)                                            │ │
│ │  ├─ email                                                    │ │
│ │  ├─ created_at                                               │ │
│ │  └─ last_login_device ✨ NEW                                 │ │
│ └─────────────────────────────────────────────────────────────┘ │
│                              │                                   │
│                              ▼                                   │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │  household_profiles                                          │ │
│ │  ├─ id (uuid, pk)                                            │ │
│ │  ├─ user_id (uuid, fk)                                       │ │
│ │  ├─ region, culture, primary_language                        │ │
│ │  ├─ favorite_cuisines[], avoided_cuisines[]                  │ │
│ │  ├─ skill_level                                              │ │
│ │  ├─ onboarding_completed_at ✨ NEW                           │ │
│ │  └─ basic_spices_available ✨ NEW                            │ │
│ └─────────────────────────────────────────────────────────────┘ │
│                              │                                   │
│                              ▼                                   │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │  family_members                                              │ │
│ │  ├─ id (uuid, pk)                                            │ │
│ │  ├─ household_profile_id (uuid, fk)                          │ │
│ │  ├─ name, age                                                │ │
│ │  ├─ allergens[]                                              │ │
│ │  ├─ dietary_restrictions[]                                   │ │
│ │  ├─ spice_tolerance                                          │ │
│ │  └─ display_order                                            │ │
│ └─────────────────────────────────────────────────────────────┘ │
│                                                                  │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │  audit_log ✨ NEW                                            │ │
│ │  ├─ id (uuid, pk)                                            │ │
│ │  ├─ user_id (uuid, fk)                                       │ │
│ │  ├─ event_type (text)                                        │ │
│ │  ├─ route (text)                                             │ │
│ │  ├─ entity_type, entity_id                                   │ │
│ │  ├─ old_value (jsonb)                                        │ │
│ │  ├─ new_value (jsonb)                                        │ │
│ │  ├─ device_info (jsonb)                                      │ │
│ │  ├─ ip_address (inet)                                        │ │
│ │  └─ created_at                                               │ │
│ │                                                              │ │
│ │  ⚠️  TRIGGER: validate_allergen_change()                     │ │
│ │     Prevents allergen removal without audit entry            │ │
│ └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

---

## Authentication Flow

```
┌──────────┐                    ┌──────────┐                    ┌──────────┐
│  Flutter │                    │  FastAPI │                    │ Supabase │
│   App    │                    │  Backend │                    │   Auth   │
└────┬─────┘                    └────┬─────┘                    └────┬─────┘
     │                               │                               │
     │  1. Login (email/password)    │                               │
     ├──────────────────────────────>│  2. Verify credentials        │
     │                               ├──────────────────────────────>│
     │                               │                               │
     │                               │  3. Return JWT token          │
     │  4. Store JWT in secure       │<──────────────────────────────┤
     │     storage                   │                               │
     │<──────────────────────────────┤                               │
     │                               │                               │
     │  5. GET /profile/full         │                               │
     │     Authorization: Bearer JWT │                               │
     ├──────────────────────────────>│  6. Validate JWT              │
     │                               │    (check signature +          │
     │                               │     extract user_id)          │
     │                               │                               │
     │  7. Return profile data       │  8. Query DB with user_id     │
     │     (user owns this data)     │    (RLS enforced)             │
     │<──────────────────────────────┤                               │
     │                               │                               │
```

---

## Onboarding Flow

```
┌────────────────────────────────────────────────────────────────┐
│                        User Opens App                           │
└────────────────────────────────┬───────────────────────────────┘
                                 │
                                 ▼
                   ┌─────────────────────────┐
                   │  GET /profile/          │
                   │  onboarding-status      │
                   └───────┬─────────────────┘
                           │
          ┌────────────────┴────────────────┐
          ▼                                 ▼
    ┌──────────┐                     ┌──────────┐
    │completed │                     │completed │
    │  = true  │                     │  = false │
    └────┬─────┘                     └────┬─────┘
         │                                │
         ▼                                ▼
  ┌──────────────┐           ┌────────────────────────┐
  │  Navigate to │           │ Check resume_step:     │
  │  Home Screen │           │ - HOUSEHOLD            │
  └──────────────┘           │ - ALLERGIES            │
                             │ - DIETARY              │
                             │ - SPICE                │
                             │ - PANTRY               │
                             │ - LANGUAGE             │
                             │ - COMPLETE             │
                             └───────┬────────────────┘
                                     │
                                     ▼
                      ┌─────────────────────────────┐
                      │ Navigate to resume_step     │
                      │ Show: "Welcome back! Resume │
                      │        from step X"         │
                      └──────────────┬──────────────┘
                                     │
                ┌────────────────────┴───────────────────┐
                │ User completes steps                   │
                │ (can "Save & Exit" at any time)        │
                └────────────────────┬───────────────────┘
                                     │
                                     ▼
                      ┌─────────────────────────────┐
                      │ Final step: LANGUAGE        │
                      │ User taps "Complete"        │
                      └──────────────┬──────────────┘
                                     │
                                     ▼
                      ┌─────────────────────────────┐
                      │ PATCH /profile/complete     │
                      │ Sets onboarding_completed_at│
                      └──────────────┬──────────────┘
                                     │
                                     ▼
                      ┌─────────────────────────────┐
                      │ Navigate to Home Screen     │
                      │ Show welcome message        │
                      └─────────────────────────────┘
```

---

## Allergen Update Flow (with Audit)

```
┌────────────────────────────────────────────────────────────────┐
│  User taps "Edit Allergens" for family member                  │
└────────────────────────────────┬───────────────────────────────┘
                                 │
                                 ▼
                   ┌─────────────────────────┐
                   │ Show allergen list UI   │
                   │ - Check/uncheck items   │
                   │ - Add custom allergens  │
                   └───────┬─────────────────┘
                           │
                           ▼
                ┌────────────────────────┐
                │ User taps "Save"       │
                └──────┬─────────────────┘
                       │
                       ▼
        ┌──────────────────────────────┐
        │ Show confirmation dialog:     │
        │ "You're updating allergens    │
        │  for [Name]. This is a        │
        │  safety-critical change.      │
        │                               │
        │ Old: [peanuts]                │
        │ New: [peanuts, shellfish]     │
        │                               │
        │ Reason (optional):            │
        │ [________________]            │
        │                               │
        │ [Cancel] [Confirm]            │
        └──────────┬───────────────────┘
                   │
                   ▼
        ┌────────────────────────────┐
        │ PATCH /profile/allergens   │
        │ {                          │
        │   member_id: "uuid",       │
        │   allergens: [...],        │
        │   reason: "Doctor visit"   │
        │ }                          │
        └──────────┬─────────────────┘
                   │
                   ▼
        ┌────────────────────────────┐
        │ Backend validates:         │
        │ 1. User owns member        │
        │ 2. JWT valid               │
        │ 3. Update database         │
        └──────────┬─────────────────┘
                   │
                   ▼
        ┌────────────────────────────┐
        │ log_audit_event()          │
        │ Stores:                    │
        │ - old_value                │
        │ - new_value                │
        │ - reason                   │
        │ - device_info              │
        │ - ip_address               │
        │ - timestamp                │
        └──────────┬─────────────────┘
                   │
                   ▼
        ┌────────────────────────────┐
        │ Return success             │
        │ Show toast: "Allergens     │
        │ updated for [Name]"        │
        └────────────────────────────┘
```

---

## Database Trigger Safety

```
┌────────────────────────────────────────────────────────────────┐
│  User attempts to UPDATE family_members.allergens              │
└────────────────────────────────┬───────────────────────────────┘
                                 │
                                 ▼
                   ┌─────────────────────────┐
                   │ TRIGGER FIRES           │
                   │ validate_allergen_change│
                   └───────┬─────────────────┘
                           │
          ┌────────────────┴────────────────┐
          ▼                                 ▼
    ┌──────────┐                     ┌──────────┐
    │ old =    │                     │ old !=   │
    │ new      │                     │ new      │
    └────┬─────┘                     └────┬─────┘
         │                                │
         ▼                                ▼
  ┌──────────────┐         ┌─────────────────────────┐
  │ Allow UPDATE │         │ Check audit_log for     │
  └──────────────┘         │ matching entry in       │
                           │ last 5 seconds          │
                           └───────┬─────────────────┘
                                   │
                  ┌────────────────┴────────────────┐
                  ▼                                 ▼
            ┌──────────┐                     ┌──────────┐
            │ Entry    │                     │ No entry │
            │ exists   │                     │ found    │
            └────┬─────┘                     └────┬─────┘
                 │                                │
                 ▼                                ▼
          ┌──────────────┐              ┌──────────────┐
          │ Allow UPDATE │              │ BLOCK UPDATE │
          └──────────────┘              │ Raise        │
                                        │ exception    │
                                        └──────────────┘
```

---

## Data Aggregation (get_full_profile)

```
┌────────────────────────────────────────────────────────────────┐
│  GET /profile/full                                              │
└────────────────────────────────┬───────────────────────────────┘
                                 │
                                 ▼
                   ┌─────────────────────────┐
                   │ get_full_profile()      │
                   └───────┬─────────────────┘
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
    ┌──────────┐   ┌───────────────┐  ┌─────────────┐
    │ Query    │   │ Query          │  │ Query       │
    │ users    │   │ household_     │  │ family_     │
    │ table    │   │ profiles       │  │ members     │
    └────┬─────┘   └───────┬───────┘  └──────┬──────┘
         │                 │                  │
         └────────┬────────┴──────────────────┘
                  │
                  ▼
        ┌──────────────────────────────┐
        │ Aggregate allergens from all │
        │ members:                     │
        │ - Combine all allergen[]     │
        │ - Remove duplicates          │
        │ - Set enforcement: "strict"  │
        └──────────────┬───────────────┘
                       │
                       ▼
        ┌──────────────────────────────┐
        │ Aggregate dietary from all   │
        │ members:                     │
        │ - Check for vegetarian       │
        │ - Check for vegan            │
        │ - Check for no_beef          │
        │ - Check for no_pork          │
        │ - Check for no_alcohol       │
        │ - Set booleans               │
        └──────────────┬───────────────┘
                       │
                       ▼
        ┌──────────────────────────────┐
        │ Return combined object:      │
        │ {                            │
        │   user: {...},               │
        │   profile: {...},            │
        │   household: {...},          │
        │   members: [...],            │
        │   allergens: {...},          │
        │   dietary: {...}             │
        │ }                            │
        └──────────────────────────────┘
```

---

## Legend

```
✨ NEW     - Feature added in Phases A, B, or C
⚠️ TRIGGER - Database trigger for safety
┌─────┐
│ Box │    - Component or action
└─────┘
  │
  ▼        - Flow direction
```

---

## Summary

- **Phase A**: Database schema with audit_log, onboarding tracking
- **Phase B**: JWT authentication across all existing endpoints
- **Phase C**: 7 new endpoints for specialized updates + onboarding
- **Next**: Phase D (Flutter SDK), E (UI screens), F (resume logic)
