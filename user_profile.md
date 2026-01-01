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

### Overview

The AI/LLM layer MUST use profile data from `GET /profile/full` to generate safe, personalized recipes and meal plans. This section defines how to construct prompts with proper safety constraints and context binding.

### 11.1 Data Source (Always Fresh)

**Rule**: Always fetch profile data immediately before AI generation

```python
# CORRECT: Fetch fresh profile data
async def generate_recipe(user_id: str):
    profile = await get_full_profile(user_id)
    prompt = build_ai_prompt(profile)
    recipe = await llm.generate(prompt)
    return recipe

# INCORRECT: Using cached or stale data
async def generate_recipe_wrong(user_id: str):
    # ❌ DON'T: Use cached profile from 1 hour ago
    profile = cache.get(f"profile:{user_id}")
    prompt = build_ai_prompt(profile)
    recipe = await llm.generate(prompt)
    return recipe
```

**Why**: Users may have just updated allergens or dietary restrictions. Stale data could cause dangerous suggestions.

---

### 11.2 Hard Constraints (MUST NEVER Violate)

**Definition**: Hard constraints are safety-critical and must ALWAYS be enforced in AI prompts. Violations could cause health issues or violate deeply held beliefs.

#### Allergens (Life-Threatening)

```python
def build_allergen_constraints(profile: dict) -> str:
    """Build allergen constraints for AI prompt"""
    
    # Get all declared allergens across all family members
    all_allergens = set()
    for member in profile.get("members", []):
        allergens = member.get("allergens", [])
        all_allergens.update(allergens)
    
    if not all_allergens:
        return "No known allergens."
    
    # Format as STRICT constraint
    allergen_list = ", ".join(sorted(all_allergens))
    return f"""
CRITICAL SAFETY CONSTRAINT - ALLERGENS:
The household has declared the following allergens: {allergen_list}

YOU MUST NEVER include ANY of these ingredients or derivatives:
{chr(10).join(f"- {allergen} (in any form)" for allergen in sorted(all_allergens))}

This is a HARD constraint. If you cannot create a recipe without these ingredients, 
respond with: "I cannot safely suggest a recipe given your allergen restrictions."
"""

# Example output:
# CRITICAL SAFETY CONSTRAINT - ALLERGENS:
# The household has declared the following allergens: dairy, peanuts
# 
# YOU MUST NEVER include ANY of these ingredients or derivatives:
# - dairy (in any form)
# - peanuts (in any form)
# 
# This is a HARD constraint...
```

#### Religious/Dietary Restrictions (Deeply Held Beliefs)

```python
def build_dietary_constraints(profile: dict) -> str:
    """Build dietary restriction constraints for AI prompt"""
    
    # Aggregate all dietary restrictions
    restrictions = set()
    for member in profile.get("members", []):
        diet = member.get("dietary_restrictions", [])
        restrictions.update(diet)
    
    if not restrictions:
        return "No dietary restrictions."
    
    # Map restrictions to AI-friendly language
    restriction_map = {
        "vegetarian": "NO meat, poultry, or seafood",
        "vegan": "NO animal products (meat, dairy, eggs, honey)",
        "no_beef": "NO beef or beef products",
        "no_pork": "NO pork or pork products",
        "no_alcohol": "NO alcohol in any form (cooking wine, extracts)",
        "halal": "Only halal meat (no pork, proper slaughter)",
        "kosher": "Only kosher ingredients (no pork, no mixing meat/dairy)",
    }
    
    constraint_text = []
    for restriction in sorted(restrictions):
        if restriction in restriction_map:
            constraint_text.append(f"- {restriction_map[restriction]}")
        else:
            constraint_text.append(f"- {restriction}")
    
    return f"""
CRITICAL DIETARY CONSTRAINTS (Religious/Ethical):
The household has the following dietary restrictions:
{chr(10).join(constraint_text)}

These are HARD constraints representing religious beliefs or ethical choices.
You MUST respect these completely. If you cannot create a compliant recipe,
respond with: "I cannot suggest a recipe that respects your dietary restrictions."
"""
```

#### Validation Before Serving Recipe

```python
async def validate_recipe_safety(recipe: dict, profile: dict) -> tuple[bool, list[str]]:
    """
    Validate recipe against hard constraints before showing to user.
    
    Returns:
        (is_safe, violations) - True if safe, list of violations if not
    """
    violations = []
    
    # Check allergens in ingredients
    all_allergens = set()
    for member in profile.get("members", []):
        all_allergens.update(member.get("allergens", []))
    
    for ingredient in recipe.get("ingredients", []):
        ingredient_lower = ingredient.lower()
        for allergen in all_allergens:
            if allergen.lower() in ingredient_lower:
                violations.append(f"Contains allergen: {allergen} in '{ingredient}'")
    
    # Check dietary restrictions
    restrictions = set()
    for member in profile.get("members", []):
        restrictions.update(member.get("dietary_restrictions", []))
    
    if "vegetarian" in restrictions or "vegan" in restrictions:
        meat_keywords = ["chicken", "beef", "pork", "fish", "shrimp", "meat"]
        for ingredient in recipe.get("ingredients", []):
            ingredient_lower = ingredient.lower()
            for meat in meat_keywords:
                if meat in ingredient_lower:
                    violations.append(f"Contains meat for vegetarian: '{ingredient}'")
    
    if "vegan" in restrictions:
        animal_keywords = ["milk", "butter", "cheese", "egg", "honey", "cream"]
        for ingredient in recipe.get("ingredients", []):
            ingredient_lower = ingredient.lower()
            for animal in animal_keywords:
                if animal in ingredient_lower:
                    violations.append(f"Contains animal product for vegan: '{ingredient}'")
    
    is_safe = len(violations) == 0
    return is_safe, violations

# Usage in API endpoint:
async def suggest_recipe(user_id: str):
    profile = await get_full_profile(user_id)
    recipe = await generate_recipe_with_ai(profile)
    
    # ALWAYS validate before returning
    is_safe, violations = await validate_recipe_safety(recipe, profile)
    
    if not is_safe:
        # Log violation for monitoring
        logger.error(f"Recipe safety violation for user {user_id}: {violations}")
        
        # DO NOT return unsafe recipe
        # Regenerate or return error
        return {
            "error": "Could not generate a safe recipe matching your restrictions",
            "retry": True
        }
    
    return recipe
```

---

### 11.3 Soft Constraints (Preferences, Not Safety)

**Definition**: Soft constraints represent preferences that SHOULD be followed but can be flexibly interpreted or occasionally relaxed.

#### Spice Tolerance

```python
def build_spice_preferences(profile: dict) -> str:
    """Build spice tolerance preferences for AI prompt"""
    
    # Get spice tolerance from members
    tolerances = []
    for member in profile.get("members", []):
        tolerance = member.get("spice_tolerance")
        if tolerance:
            tolerances.append(tolerance)
    
    if not tolerances:
        return "No spice preference specified. Use medium spice level."
    
    # Map tolerance to AI guidance
    tolerance_map = {
        "none": "completely mild with no spices or heat",
        "mild": "gently seasoned with minimal heat",
        "medium": "moderately spiced with balanced flavors",
        "high": "well-spiced with noticeable heat",
        "very_high": "intensely spicy with bold heat"
    }
    
    # Use most restrictive tolerance (accommodate everyone)
    primary_tolerance = min(tolerances, key=lambda x: ["none", "mild", "medium", "high", "very_high"].index(x) if x in ["none", "mild", "medium", "high", "very_high"] else 2)
    
    guidance = tolerance_map.get(primary_tolerance, "moderately spiced")
    
    return f"""
SPICE PREFERENCE (Soft Constraint):
The household prefers: {primary_tolerance.upper()} spice level
Interpretation: Create recipes that are {guidance}.

This is a PREFERENCE - you can suggest slight variations (e.g., "add more chili if desired")
but the base recipe should match their preference.
"""
```

#### Pantry Basics

```python
def build_pantry_context(profile: dict) -> str:
    """Build pantry availability context for AI prompt"""
    
    household = profile.get("household", {})
    basic_spices = household.get("basic_spices_available")
    
    if basic_spices == "yes":
        return """
PANTRY AVAILABILITY:
User has basic spices available (salt, pepper, garlic powder, onion powder, paprika, cumin, etc.)
You can assume these are on hand without listing them in shopping lists.
"""
    elif basic_spices == "some":
        return """
PANTRY AVAILABILITY:
User has SOME basic spices. Include common spices (salt, pepper, garlic) but list specialty spices 
in shopping list (cumin, paprika, herbs, etc.)
"""
    elif basic_spices == "no":
        return """
PANTRY AVAILABILITY:
User prefers simple cooking without many spices. Keep recipes simple with minimal seasoning.
If spices are needed, include ALL spices in shopping list (even salt and pepper).
"""
    else:
        return """
PANTRY AVAILABILITY:
Pantry status unknown. Assume moderate spice availability but include specialty items in shopping list.
"""
```

#### Cuisine Preferences

```python
def build_cuisine_preferences(profile: dict) -> str:
    """Build cuisine preferences for AI prompt"""
    
    household = profile.get("household", {})
    favorite_cuisines = household.get("favorite_cuisines", [])
    avoided_cuisines = household.get("avoided_cuisines", [])
    
    context_parts = []
    
    if favorite_cuisines:
        cuisines_list = ", ".join(favorite_cuisines)
        context_parts.append(f"""
PREFERRED CUISINES (Soft Preference):
User enjoys: {cuisines_list}
When possible, suggest recipes from these cuisines or with similar flavor profiles.
""")
    
    if avoided_cuisines:
        avoided_list = ", ".join(avoided_cuisines)
        context_parts.append(f"""
AVOIDED CUISINES (Preference):
User tends to avoid: {avoided_list}
Try to avoid these unless specifically requested, but this is not a hard restriction.
""")
    
    if not context_parts:
        return "No cuisine preferences specified. Suggest diverse options."
    
    return "\n".join(context_parts)
```

---

### 11.4 Complete Prompt Construction

**Full Example**: Combining all constraints for AI generation

```python
async def build_complete_ai_prompt(
    user_id: str,
    request_type: str = "dinner",
    additional_context: str = ""
) -> str:
    """
    Build complete AI prompt with all profile context and constraints.
    
    Args:
        user_id: User UUID
        request_type: "breakfast", "lunch", "dinner", "snack", "dessert"
        additional_context: User's free-form request (e.g., "something quick")
    
    Returns:
        Complete prompt string for LLM
    """
    
    # 1. Fetch fresh profile data
    profile = await get_full_profile(user_id)
    
    # 2. Build constraint sections
    allergen_constraints = build_allergen_constraints(profile)
    dietary_constraints = build_dietary_constraints(profile)
    spice_preferences = build_spice_preferences(profile)
    pantry_context = build_pantry_context(profile)
    cuisine_preferences = build_cuisine_preferences(profile)
    
    # 3. Build household context
    household = profile.get("household", {})
    members = profile.get("members", [])
    
    household_context = f"""
HOUSEHOLD CONTEXT:
- Household name: {household.get('household_name', 'Family')}
- Number of people: {len(members)}
- Member ages: {', '.join(str(m.get('age', 'unknown')) for m in members)}
- Primary language: {household.get('primary_language', 'en')}
- Measurement system: {household.get('measurement_system', 'imperial')}
"""
    
    # 4. Build request context
    request_context = f"""
USER REQUEST:
Type: {request_type.upper()} recipe
Additional context: {additional_context or "None provided"}
"""
    
    # 5. Build complete prompt
    prompt = f"""
You are SAVO, an AI cooking assistant helping a household with meal planning and recipe suggestions.

{household_context}

{allergen_constraints}

{dietary_constraints}

{spice_preferences}

{pantry_context}

{cuisine_preferences}

{request_context}

INSTRUCTIONS:
1. Generate a recipe that STRICTLY respects all CRITICAL constraints (allergens, dietary)
2. Follow preferences (spice, cuisine) as closely as possible
3. Format response as JSON with: title, description, ingredients (with quantities), 
   steps (numbered), prep_time, cook_time, servings, difficulty
4. If you cannot create a safe recipe, respond with an error message explaining why

Generate the recipe now:
"""
    
    return prompt
```

**Usage Example**:

```python
# In recipe suggestion endpoint
@router.post("/recipes/suggest")
async def suggest_recipe(
    request: RecipeSuggestionRequest,
    user_id: str = Depends(get_current_user)
):
    try:
        # Build prompt with full profile context
        prompt = await build_complete_ai_prompt(
            user_id=user_id,
            request_type=request.meal_type,
            additional_context=request.user_input
        )
        
        # Call LLM
        llm_response = await llm_client.generate(
            prompt=prompt,
            temperature=0.7,
            max_tokens=2000
        )
        
        # Parse recipe from response
        recipe = parse_recipe_from_llm(llm_response)
        
        # CRITICAL: Validate safety
        is_safe, violations = await validate_recipe_safety(recipe, profile)
        
        if not is_safe:
            logger.error(f"Unsafe recipe generated: {violations}")
            return {
                "error": "Could not generate a safe recipe",
                "reason": "Generated recipe violated safety constraints",
                "retry_allowed": True
            }
        
        # Log successful generation for audit
        await log_recipe_generation(
            user_id=user_id,
            recipe_id=recipe.get("id"),
            prompt_hash=hash(prompt),
            safety_validation="passed"
        )
        
        return {
            "success": True,
            "recipe": recipe
        }
        
    except Exception as e:
        logger.error(f"Recipe generation failed: {e}")
        raise HTTPException(status_code=500, detail="Recipe generation failed")
```

---

### 11.5 Error Handling & Fallbacks

#### Incomplete Profile Data

```python
def validate_profile_completeness(profile: dict) -> tuple[bool, list[str]]:
    """
    Check if profile has minimum required data for AI generation.
    
    Returns:
        (is_complete, missing_fields)
    """
    missing = []
    
    # Check critical fields
    if not profile.get("household"):
        missing.append("household profile")
    
    if not profile.get("members") or len(profile["members"]) == 0:
        missing.append("family members")
    
    # Allergens are REQUIRED to be explicitly declared (even if empty)
    allergens_declared = False
    for member in profile.get("members", []):
        if "allergens" in member:
            allergens_declared = True
            break
    
    if not allergens_declared:
        missing.append("allergen declarations (required for safety)")
    
    is_complete = len(missing) == 0
    return is_complete, missing

# Usage:
async def generate_recipe_safe(user_id: str):
    profile = await get_full_profile(user_id)
    
    is_complete, missing = validate_profile_completeness(profile)
    
    if not is_complete:
        return {
            "error": "Profile incomplete",
            "message": "Please complete your profile before generating recipes",
            "missing_fields": missing,
            "onboarding_required": True
        }
    
    # Proceed with generation...
```

#### LLM Failure Recovery

```python
async def generate_recipe_with_fallback(
    user_id: str,
    max_retries: int = 3
) -> dict:
    """
    Generate recipe with automatic retries and fallback strategies.
    """
    
    profile = await get_full_profile(user_id)
    
    for attempt in range(max_retries):
        try:
            # Build prompt
            prompt = await build_complete_ai_prompt(user_id)
            
            # Add retry context if not first attempt
            if attempt > 0:
                prompt += f"\n\nNOTE: This is retry {attempt + 1}. Previous attempts failed validation."
            
            # Generate
            recipe = await llm_client.generate(prompt)
            
            # Validate
            is_safe, violations = await validate_recipe_safety(recipe, profile)
            
            if is_safe:
                return {"success": True, "recipe": recipe}
            else:
                logger.warning(f"Retry {attempt + 1}: Safety violations: {violations}")
                continue
                
        except Exception as e:
            logger.error(f"Attempt {attempt + 1} failed: {e}")
            continue
    
    # All retries exhausted - use fallback
    return await get_fallback_recipe(profile)

async def get_fallback_recipe(profile: dict) -> dict:
    """
    Return a safe, pre-validated recipe from database as fallback.
    Filter by user's constraints.
    """
    
    # Query recipe database for recipes matching user constraints
    recipes = await query_recipes_matching_constraints(profile)
    
    if recipes:
        return {"success": True, "recipe": recipes[0], "source": "database"}
    
    # Ultimate fallback: return error
    return {
        "success": False,
        "error": "Could not generate a safe recipe",
        "message": "Please try again or contact support"
    }
```

---

### 11.6 Monitoring & Observability

#### Track Constraint Violations

```python
async def log_constraint_violation(
    user_id: str,
    recipe_id: str,
    violation_type: str,
    violation_details: dict
):
    """
    Log constraint violations for monitoring and improvement.
    """
    
    await log_event(
        event_type="ai_constraint_violation",
        user_id=user_id,
        data={
            "recipe_id": recipe_id,
            "violation_type": violation_type,  # "allergen", "dietary", "validation_error"
            "details": violation_details,
            "timestamp": datetime.utcnow().isoformat()
        }
    )
    
    # Alert if safety violation (allergen)
    if violation_type == "allergen":
        await send_alert(
            severity="critical",
            message=f"Allergen violation detected for user {user_id}",
            details=violation_details
        )
```

#### Metrics to Track

```python
# Track these metrics for AI generation quality:

1. Safety Validation Pass Rate
   - % of generated recipes that pass safety validation on first try
   - Target: >99% for allergen safety, >95% for dietary

2. Retry Rate
   - % of recipe generations requiring retries
   - Target: <5%

3. Fallback Rate
   - % of requests using fallback recipes instead of AI generation
   - Target: <1%

4. User Satisfaction
   - Track user ratings of AI-generated recipes
   - Track rejection/regeneration requests
   - Target: >4.2/5.0 average rating

5. Profile Completeness
   - % of users with complete profiles (all constraints declared)
   - Target: >90% after onboarding

6. Constraint Violation Alerts
   - Count of critical violations (should be ZERO in production)
   - Any allergen violation = immediate investigation
```

---

### 11.7 Testing Requirements

#### Unit Tests for Constraint Building

```python
def test_allergen_constraints():
    """Test allergen constraint generation"""
    profile = {
        "members": [
            {"allergens": ["peanuts", "dairy"]},
            {"allergens": ["shellfish"]}
        ]
    }
    
    constraints = build_allergen_constraints(profile)
    
    # Verify all allergens included
    assert "peanuts" in constraints
    assert "dairy" in constraints
    assert "shellfish" in constraints
    
    # Verify strict language
    assert "MUST NEVER" in constraints
    assert "CRITICAL" in constraints

def test_safety_validation():
    """Test recipe safety validation"""
    profile = {
        "members": [{"allergens": ["peanuts"]}]
    }
    
    # Safe recipe
    safe_recipe = {
        "ingredients": ["chicken", "rice", "broccoli"]
    }
    is_safe, violations = validate_recipe_safety(safe_recipe, profile)
    assert is_safe
    assert len(violations) == 0
    
    # Unsafe recipe
    unsafe_recipe = {
        "ingredients": ["peanut butter", "bread", "jelly"]
    }
    is_safe, violations = validate_recipe_safety(unsafe_recipe, profile)
    assert not is_safe
    assert len(violations) > 0
    assert any("peanut" in v.lower() for v in violations)
```

#### Integration Tests

```python
async def test_end_to_end_recipe_generation():
    """Test complete recipe generation flow with safety validation"""
    
    # Create test user with allergens
    user_id = await create_test_user(allergens=["dairy"])
    
    # Generate recipe
    result = await generate_recipe_with_fallback(user_id)
    
    # Verify success
    assert result["success"]
    recipe = result["recipe"]
    
    # Verify no dairy in ingredients
    ingredients_text = " ".join(recipe["ingredients"]).lower()
    assert "milk" not in ingredients_text
    assert "cheese" not in ingredients_text
    assert "butter" not in ingredients_text
    
    # Cleanup
    await delete_test_user(user_id)
```

---

### 11.8 Summary of Best Practices

✅ **DO:**
- Always fetch fresh profile data before AI generation
- Treat allergens and dietary restrictions as HARD constraints (never violate)
- Validate ALL generated recipes against constraints before serving
- Log all constraint violations for monitoring
- Provide clear error messages when constraints cannot be satisfied
- Use retries with modified prompts if first generation fails validation
- Monitor metrics to track AI safety and quality

❌ **DON'T:**
- Use cached or stale profile data
- Assume user preferences without checking DB
- Skip safety validation "just this once"
- Serve recipes that violate allergen constraints under any circumstance
- Ignore soft constraints completely (they improve user experience)
- Generate recipes without household context
- Trust AI output blindly - always validate

---

### 11.9 Example Prompt Templates

#### For Daily Meal Planning

```python
PROMPT_TEMPLATE_DAILY = """
You are SAVO, helping plan dinner for the {household_name} household.

{allergen_constraints}
{dietary_constraints}

HOUSEHOLD DETAILS:
- Members: {member_count} people
- Ages: {member_ages}
- Preferred cuisines: {favorite_cuisines}
- Spice preference: {spice_level}

TODAY'S CONTEXT:
- Day of week: {day_of_week}
- Season: {season}
- Available cooking time: {cooking_time}

Generate a dinner recipe that:
1. Feeds {member_count} people
2. Takes no more than {cooking_time} minutes total time
3. Uses seasonal {season} ingredients when possible
4. STRICTLY avoids all allergens and respects dietary restrictions

Respond with JSON format recipe.
"""
```

#### For Weekly Meal Prep

```python
PROMPT_TEMPLATE_WEEKLY = """
You are SAVO, creating a weekly meal plan for the {household_name} household.

{allergen_constraints}
{dietary_constraints}

HOUSEHOLD DETAILS:
- Members: {member_count}
- Pantry basics available: {pantry_status}
- Cooking skill: {skill_level}

WEEKLY PLAN REQUIREMENTS:
- 7 dinners for the week
- Variety of cuisines: {favorite_cuisines}
- Include 2 batch cooking recipes (make once, eat twice)
- Balance cooking times (mix quick and involved recipes)
- Minimize ingredient overlap for shopping efficiency

CRITICAL: Every recipe must be safe for all household members. Never include allergens.

Generate weekly plan as JSON array of 7 recipes.
"""
```

---

**Phase 11 Complete** ✅

This comprehensive guide ensures the AI layer generates safe, personalized recipes while respecting all user constraints and preferences.
