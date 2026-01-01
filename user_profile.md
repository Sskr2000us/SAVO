# SAVO — User Profile (Auth + Onboarding + DB Persistence)

**Date:** January 1, 2026  
**Scope:** Implement the JSON spec end-to-end (DB → API → Flutter UI), ensuring **all changes persist**, **data is fetched from DB**, onboarding can **resume**, allergen edits are **safety-gated + audited**, and auth supports **multi-device sessions**.

---

## 0) What exists today (baseline)

- Flutter already has `shared_preferences` and a Settings screen that **reads/writes** profile data via the backend, but uses hardcoded `X-User-Id` headers.
- Backend already has:
  - Supabase DB client: `services/api/app/core/database.py`
  - Household + family member endpoints: `services/api/app/api/routes/profile.py`
  - Supabase schema with `public.users`, `public.household_profiles`, `public.family_members` in `services/api/migrations/001_initial_schema.sql`

Your JSON spec uses tables named `households`, `user_profiles`, etc. The current repo schema uses `household_profiles` and `family_members`. This plan maps the spec to the existing schema (minimal churn), and adds missing fields/tables via migrations.

---

## 1) Data model mapping (JSON spec → current DB)

### 1.1 Tables

**Spec** → **Repo DB**
- `users` → `public.users` (already exists; fields are close)
- `households` → `public.household_profiles` (treat this as the household record; it’s 1:1 per user in current schema)
- `user_profiles` → `public.household_profiles` + `public.family_members` (profile fields already live here)
- `household_members` → `public.family_members`
- `allergen_profiles` → `public.family_members.allergens[]` (per-member) + optional household-level mirror if desired
- `dietary_rules` → `public.family_members.dietary_restrictions[]` (per-member) + optional household-level booleans if desired

### 1.2 Field mapping

**Spec field** → **Repo field**
- `language` → `household_profiles.primary_language`
- `measurement_system` → `household_profiles.measurement_system`
- `spice_tolerance` → `family_members.spice_tolerance`
- `basic_spices_available` → store in `household_profiles` (add column) OR use existing JSON fields if preferred
- `preferred_cuisines` → `household_profiles.favorite_cuisines`
- `health_conditions` → `family_members.health_conditions[]`

### 1.3 New fields required by the spec (add via migration)

- `household_profiles.onboarding_completed_at TIMESTAMPTZ` (resume + gating)
- `household_profiles.basic_spices_available TEXT` with constraint `('yes','some','no')`
- `audit_log` table (for “every write logged”, and allergen safety logging)

---

## 2) Phase A — Database changes (Supabase SQL)

### Step A1 — Add migration `002_user_profile_spec.sql`

Create: `services/api/migrations/002_user_profile_spec.sql`

- Add onboarding tracking:
  - `ALTER TABLE public.household_profiles ADD COLUMN onboarding_completed_at TIMESTAMPTZ;`
- Add pantry/basic spices availability:
  - `ALTER TABLE public.household_profiles ADD COLUMN basic_spices_available TEXT;`
  - Add CHECK constraint: `basic_spices_available IN ('yes','some','no')`
- Create `public.audit_log`:
  - Columns: `id`, `user_id`, `event_type`, `route`, `entity_type`, `entity_id`, `old_value JSONB`, `new_value JSONB`, `device_info JSONB`, `created_at`
  - Index on `(user_id, created_at desc)`
  - Enable RLS; allow select for `auth.uid() = user_id` (users can review), and allow insert from backend service

Acceptance:
- You can `SELECT onboarding_completed_at, basic_spices_available FROM public.household_profiles;`
- `SELECT * FROM public.audit_log LIMIT 1;` works.

---

## 3) Phase B — Backend auth: move to Bearer tokens (production)

### Goal
Replace `X-User-Id` / `X-User-Email` with `Authorization: Bearer <supabase_jwt>`.

### Step B1 — Add auth dependency

Create: `services/api/app/middleware/auth.py`
- Validate Supabase JWT
- Extract `user_id` from `sub`

Config:
- Add `SUPABASE_JWT_SECRET` (or JWKS validation if you prefer). Keep it server-side.

### Step B2 — Refactor profile routes to use `Depends(get_current_user)`

Update: `services/api/app/api/routes/profile.py`
- Replace all `x_user_id: Header(...)` with `user_id: Depends(get_current_user)`
- Stop trusting client-provided user IDs

Acceptance:
- Calling endpoints without `Authorization` returns 401
- Calling with a valid token hits the correct user’s rows

---

## 4) Phase C — Backend API: implement JSON endpoints + fetch/update cycle

Your spec requires:
- `GET /profile/full`
- write endpoints that update DB
- after each submit: refetch `GET /profile/full`

### Step C1 — Implement `GET /profile/full`

Add to: `services/api/app/api/routes/profile.py`
- Returns:
  - `user` from `public.users`
  - `profile` (use `household_profiles` + computed fields)
  - `household` (same as `household_profiles` in current schema)
  - `members` from `family_members`
  - `allergens` (aggregate view; e.g., union across members)
  - `dietary` (aggregate view; union / boolean projection)

Acceptance:
- A single call returns all fields needed for UI state hydration.

### Step C2 — Implement write endpoints per JSON

All should:
1) read existing record (for audit old_value)
2) write the update
3) write audit_log entry
4) return success

Implement endpoints:
- `PATCH /profile/household`
  - payload: list of members
  - DB: upsert into `family_members` (role mapping: adult/child/senior)
- `PATCH /profile/allergens`
  - payload: `declared_allergens[]`
  - Apply to selected members OR household-wide default (choose simplest: apply to all members unless UI selects member)
  - Special rules: `none` exclusive
- `PATCH /profile/dietary`
  - payload: booleans + religious constraints
  - Map to `family_members.dietary_restrictions[]` (e.g. `vegetarian`, `no_beef`, etc.) and store `religious_constraints[]` either as restrictions or add a household-level column if you want strict fidelity
- `PATCH /profile/preferences`
  - payload: `spice_tolerance`, `basic_spices_available`, `preferred_cuisines[]`
  - DB:
    - `family_members.spice_tolerance` (apply to “owner” member or all; simplest: owner/all)
    - `household_profiles.basic_spices_available`
    - `household_profiles.favorite_cuisines`
- `PATCH /profile/language`
  - payload: `language`, `measurement_system`
  - DB: `household_profiles.primary_language`, `measurement_system`

### Step C3 — Add onboarding status + completion

Endpoints:
- `GET /profile/onboarding-status`
  - returns `{ completed, resume_step, missing_fields }`
- `PATCH /profile/complete`
  - sets `onboarding_completed_at = now()`

Resume logic (server-side):
- If no household profile → resume at HOUSEHOLD
- If members empty → HOUSEHOLD
- If allergens not declared (explicitly require) → ALLERGIES
- If dietary not declared → DIETARY
- If spice_tolerance missing → SPICE (optional)
- If basic_spices_available missing → PANTRY (optional)
- If primary_language missing → LANGUAGE

Acceptance:
- Closing/reopening the app returns a deterministic resume step.

---

## 5) Phase D — Flutter: session persistence + API auth header

### Step D1 — Add Supabase SDK

Update: `apps/mobile/pubspec.yaml`
- Add `supabase_flutter`

### Step D2 — Initialize Supabase with SDK persistence

Update: `apps/mobile/lib/main.dart`
- `persistSession: true`
- Keep SDK-managed secure session storage
- Add manual refresh on resume:
  - on app resume: attempt `refreshSession()`; if fails → logout + go to LOGIN

### Step D3 — Update API client to send Bearer token

Update: `apps/mobile/lib/services/api_client.dart`
- Add `Authorization: Bearer <accessToken>` header for all requests when authenticated
- Remove hardcoded `X-User-Id`

Acceptance:
- App restart stays logged-in
- Backend rejects unauthenticated requests

---

## 6) Phase E — Flutter UI: onboarding flow (LOGIN → COMPLETE)

Implement screens in: `apps/mobile/lib/screens/onboarding/`

### Step E1 — LOGIN screen
- Email OTP, Google, Apple
- On success: call `GET /profile/full` and `GET /profile/onboarding-status`

### Step E2 — HOUSEHOLD
- Multi-select “Just me / Adults / Kids / Seniors”
- Map to `PATCH /profile/household` payload
- After submit: refetch `GET /profile/full`

### Step E3 — ALLERGIES (blocking)
- Multi-select allergens + None exclusive
- Submit to `PATCH /profile/allergens`
- After submit: refetch

### Step E4 — DIETARY
- Multi-select dietary + None
- Submit to `PATCH /profile/dietary`
- After submit: refetch

### Step E5 — SPICE (optional, skippable)
- Single select mild/medium/spicy/depends
- Submit to `PATCH /profile/preferences` (or a dedicated endpoint)
- Allow Skip:
  - choose default `depends` (or keep null)

### Step E6 — PANTRY (optional, skippable)
- Single select yes/some/no
- Submit to `PATCH /profile/preferences`
- Allow Skip:
  - choose default `some` (or keep null)

### Step E7 — LANGUAGE (optional, skippable but recommended)
- Default to device language
- Measurement metric/imperial
- Submit to `PATCH /profile/language`
- Allow Skip:
  - set language to device default and measurement to device region default

### Step E8 — COMPLETE
- CTA Start Cooking
- Call `PATCH /profile/complete`

Acceptance:
- Every Next/Save writes to DB
- Every submit refetches `GET /profile/full` and updates local state

---

## 7) Phase F — Onboarding partial completion (resume)

### Step F1 — Client-side backup with SharedPreferences

Store:
- `onboarding_last_step` (int)
- Updated on each successful submit

Resume precedence:
1) Use server `GET /profile/onboarding-status`
2) If server fails (offline), fallback to `onboarding_last_step`

Acceptance:
- Kill app mid-onboarding, reopen → resumes correctly

---

## 8) Phase G — Allergen editing restrictions + audit

### Step G1 — UI restriction on allergen removal

Update: `apps/mobile/lib/screens/settings_screen.dart`
- When user attempts to remove an allergen:
  - show confirmation dialog:
    - “Are you sure? SAVO will start including [allergen] in suggestions.”
  - require explicit confirm

### Step G2 — Audit every write (server-side)

On every PATCH endpoint:
- Write `audit_log`:
  - `event_type` like `profile_write`
  - `route` like `/profile/allergens`
  - `old_value` / `new_value`
  - `device_info` from client

Acceptance:
- Audit rows appear for all writes
- User can review via `GET /profile/audit` (optional endpoint) or direct DB query

---

## 9) Phase H — Multi-device session sync + “Active Sessions”

### Step H1 — Session behavior
- Supabase Auth handles token refresh per device
- Sessions remain valid unless revoked

### Step H2 — Settings → Active Sessions screen

Add screen: `apps/mobile/lib/screens/settings/active_sessions_screen.dart`
- Show current session metadata (device + last login)
- Add button: “Sign out all other devices”
  - Use Supabase sign out scope `others` (via SDK)

Backend note:
- If you also want server visibility, store `last_login_device` and optionally `active_sessions_count` in `public.users`

Acceptance:
- Signing out “others” logs out other devices but keeps current

---

## 10) Testing checklist (must pass)

### Backend
- `GET /profile/full` returns correct shape
- All PATCH endpoints:
  - update DB
  - log audit
  - require Bearer token

### Flutter
- Login persists after app restart
- Each onboarding step writes + refetches
- Mid-onboarding resume works
- Allergen removal shows confirmation dialog
- Active sessions screen can sign out other devices

---

## 11) Notes on safety + AI context binding

When building prompts for the AI layer:
- Hard constraints: allergens + religious rules (never violated)
- Soft constraints: spice tolerance, pantry basics
- Always source profile values from `GET /profile/full` (DB is source of truth)
