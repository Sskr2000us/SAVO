# SAVO — End-to-End Build Action Items (Step-by-Step)

This checklist is derived from:
- [docs/Build_Plan.md](Build_Plan.md)
- [docs/Software_Architecture.md](Software_Architecture.md)
- [docs/spec/engineering-plan.mvp.json](spec/engineering-plan.mvp.json)
- [docs/spec/prompt-pack.gpt-5.2.json](spec/prompt-pack.gpt-5.2.json)
- [docs/spec/ui-spec.ant.figma-ready.json](spec/ui-spec.ant.figma-ready.json)

**Your decisions captured here**
- Mobile stack: **Flutter** (existing in `apps/mobile/`)
- MVP planning: **Daily + Party + Weekly**
- Weekly: **anchored to `start_date`**, and `num_days` is configurable
- Party: **age toggles affect recipe selection** in MVP
- Cook Mode: **timers-only**, user-tap-to-start, with **per-step timers + overall recipe timer**

---

## 0) Finalize remaining inputs (blockers)

> These are now locked so you can implement contracts immediately.

- [x] Weekly horizon
  - [x] Anchored to `start_date`
  - [x] `num_days` allowed range: `1..4` (default `4`)
  - [x] Timezone source: `app_configuration.timezone` (preferred), fallback to `session_request.timezone`, final fallback to device timezone
- [x] Party age inputs (explicit)
  - [x] `party_settings.guest_count: int (2..80)`
  - [x] `party_settings.age_group_counts` (integers that must sum to `guest_count`):
    - `child_0_12: 0..guest_count`
    - `teen_13_17: 0..guest_count`
    - `adult_18_plus: 0..guest_count`
  - [x] Derived behavior rule: if `child_0_12 > 0` then enforce kid-friendly options and mild spice guidance.

---

## 1) Update the JSON specs (source-of-truth)

### 1.1 Weekly planning: make horizon configurable
- [x] Update [docs/spec/prompt-pack.gpt-5.2.json](spec/prompt-pack.gpt-5.2.json)
  - [x] Modify `TASK_PLAN_WEEKLY` prompt text to accept `start_date`, `num_days`, `timezone` instead of hard-coded "7-day"
  - [x] Ensure `TASK_PLAN_WEEKLY` bindings include config + units (align with system constraints)
    - Must include: `{{APP_CONFIGURATION}}`, `{{MEASUREMENT_SYSTEM}}`, `{{OUTPUT_LANGUAGE}}`, `{{TIME_AVAILABLE_MIN}}`, `{{SERVINGS}}` (as appropriate)
  - [x] Timezone priority: `app_configuration.timezone` (preferred) → `session_request.timezone` → device timezone
- [x] Extend `MENU_PLAN_SCHEMA` to support weekly day identity and planning window
  - [x] Add top-level:
    - `planning_window: { start_date: string(YYYY-MM-DD), num_days: number, timezone: string }`
  - [x] For `menus[*]` where `menu_type == "weekly_day"`, add:
    - `day_index: number`
    - `date: string(YYYY-MM-DD)`
- [x] Update [docs/spec/ui-spec.ant.figma-ready.json](spec/ui-spec.ant.figma-ready.json)
  - [x] Replace `weekly_planner_widgets.week_strip.days` (fixed Mon–Sun) with a variable-length date strip derived from `planning_window`
  - [x] Keep UI behavior: tap day -> open S3 filtered, but now filter by `date` or `day_index`
- [x] Update [docs/spec/engineering-plan.mvp.json](spec/engineering-plan.mvp.json)
  - [x] Replace E4-S3 wording/AC from "7-day" to "N-day anchored plan"

###x] Update [docs/spec/prompt-pack.gpt-5.2.json](spec/prompt-pack.gpt-5.2.json)
  - [x] Define how `{{PARTY_SETTINGS}}` includes age fields/preset
  - [x] Update `TASK_PLAN_PARTY_MENU` prompt to enforce kid-aware selection (spice/texture + at-least-one-kid-friendly option)
- [x] Update [docs/spec/ui-spec.ant.figma-ready.json](spec/ui-spec.ant.figma-ready.json)
  - [x] Replace "age distribution quick toggles" with explicit toggle labels matching the chosen contract
- [x] Update [docs/spec/engineering-plan.mvp.json](spec/engineering-plan.mvp.json)
  - [xUpdate [docs/spec/engineering-plan.mvp.json](spec/engineering-plan.mvp.json)
  - [ ] Update E4-S2 acceptance criteria to include: "Age toggles influence recipe options + instructions"

### 1.3 Cook Mode timers (UI + acceptance criteria)
- [x] Update [docs/spec/engineering-plan.mvp.json](spec/engineering-plan.mvp.json)
  - [x] Update E5-S1 acceptance criteria:
    - Per-step timers shown when `time_minutes > 0`
    - User must tap to start
    - Overall recipe timer shown based on `estimated_times.total_minutes`
- [ ] (Optional) If you want richer timer semantics later, add new schema fields (not required for MVP): `timer_hint`, `auto_start`.

---

## 2) Backend (FastAPI) — implement contracts + endpoints end-to-end

Backend lives in [services/api](../services/api).

### 2.1 Local dev setup
- [x] Create venv + install deps (PowerShell)
  - [x] `cd services\api`
  - [x] `python -m venv .venv`
  - [x] `./.venv/Scripts/Activate.ps1`
  - [x] `pip install -r requirements.txt`
- [x] Run API in mock mode
  - [x] `$env:SAVO_LLM_PROVIDER="mock"`
  - [x] `uvicorn app.main:app --reload --port 8000`
  - [x] Verify `GET http://localhost:8000/health`

### 2.2 Lock request DTOs (Pydantic models) for each endpoint
- [x] Define `app_configuration` model (E1)
- [x] Define `inventory` model (E2)
- [x] Define `session_request` model
  - [x] daily: `time_available_minutes`, `servings`, `selected_cuisine?`
  - [x] party: include `party_settings` (guest_count + age inputs)
  - [x] weekly: include `start_date`, `num_days`, `timezone`

### 2.3 Implement orchestration rules (deterministic, backend-owned)
- [x] Repetition controls (`avoid_repetition_days`, rotate cuisines/methods)
- [x] Prefer expiring ingredients
- [x] Weekly rules: max repeats, leftover reuse within X days (keep X configurable, default 2)
- [x] Party scaling: apply 10% buffer to guest scaling rule
- [x] Hallucination guard: every `ingredients_used[*].inventory_id` must exist in inventory

### 2.4 AI orchestration reliability (schema-first, fail-closed)
- [x] Confirm prompt pack loading path (already wired via `SAVO_PROMPT_PACK_PATH`)
- [x] Enforce schema validation for every LLM response (already in `validate_json`)
- [x] Add "retry once on invalid JSON" behavior
  - [x] If the model returns non-JSON or schema invalid: send one corrective retry
  - [x] If still invalid: return `status="needs_clarification"` with questions or `status="error"`

### 2.5 Implement endpoints to match Build Plan
- [x] `/config` (GET/PUT)
- [x] `/inventory` (GET/POST/PUT/DELETE)
- [x] `/inventory/normalize` (POST) -> `NORMALIZATION_OUTPUT_SCHEMA`
- [x] `/cuisines` (GET) -> 10 cuisines + daily/party structures
- [x] `/plan/daily` (POST) -> `MENU_PLAN_SCHEMA`
- [x] `/plan/party` (POST) -> `MENU_PLAN_SCHEMA` (age toggles enforced)
- [x] `/plan/weekly` (POST) -> `MENU_PLAN_SCHEMA` + `planning_window` + `date/day_index`
- [x] `/history/recipes` (POST) -> record completion + selection
- [x] `/youtube/rank` (POST) -> `YOUTUBE_RANK_SCHEMA`

### 2.6 Persistence (pick MVP level)
- [x] MVP-0 (fastest): in-memory storage for config/inventory/history
- [ ] MVP-1 (recommended): Postgres for config/inventory/history/plans; Redis optional
  - [ ] Create migrations (Alembic or SQL scripts)
  - [ ] Store plan requests/responses for debugging and repeatability

---

## 3) Mobile (Flutter) — implement screens and wire to API

Mobile app lives in [apps/mobile](../apps/mobile).

### 3.1 Flutter setup
- [x] Confirm Flutter SDK exists and app structure ready
- [x] Updated dependencies: provider, intl, shared_preferences

### 3.2 App shell + navigation
- [x] Implement bottom nav: Home / Plan / Cook / Leftovers / Settings (S1/S2/S7/S8/S9)
- [x] Implement API client with platform-specific base URL (Android: 10.0.2.2, iOS/web: localhost)
- [x] Created all data models: config, inventory, planning, cuisine

### 3.3 Settings (S9) — config first
- [x] Built S9 Settings UI with household profile, preferences, behavior settings
- [x] Wired to `/config` GET/PUT
- [x] Includes navigation to Inventory screen

### 3.4 Inventory (S2)
- [x] Inventory list with expiring items highlighted (orange), leftover marking (blue)
- [x] Wire to `/inventory` CRUD with add/delete functionality
- [x] Highlight expiring items (orange cards) and leftovers (blue)

### 3.5 Planning results (S3)
- [x] Call `/plan/daily` and render `MENU_PLAN_SCHEMA`
- [x] Cuisine selector dropdown (loads from `/cuisines`)
- [x] Render menu headers and course sections
- [x] Render 2–3 recipe cards per course (horizontal scroll)
- [x] Sticky bottom bar: "Start Cooking" CTA

### 3.6 Weekly planner (S5) — variable horizon
- [x] UI inputs: pick `start_date` + `num_days` (1-4)
- [x] Call `/plan/weekly` with start_date and num_days
- [x] Display planning summary card showing selected parameters
- [x] Render results in PlanningResultsScreen with per-day sections

### 3.7 Party planner (S6) — guest slider + age toggles
- [x] Guest slider (2..80)
- [x] Age stepper inputs (`child_0_12`, `teen_13_17`, `adult_18_plus`)
- [x] Validation: age groups must sum to guest_count
- [x] Call `/plan/party` with party_settings
- [x] Display validation feedback (error if sum mismatch, success if valid)

### 3.8 Recipe detail + Cook mode (S4 + S7)
- [x] S4: recipe details + badges (time, difficulty, cuisine, cooking method)
- [x] S4: ingredients list with checkboxes
- [x] S4: steps preview (first 3 steps)
- [x] S7: stepper UI with current step display
- [x] S7: per-step timer from `steps[*].time_minutes` (user tap to start)
- [x] S7: overall recipe timer from start of cook mode (continuous counting)
- [x] S7: Add +1 minute button for step timers
- [x] S7: Step completion dialog with auto-advance option
- [x] S7: Finish -> `POST /history/recipes` with timestamp and metadata

### 3.9 Leftovers center (S8)
- [x] Render leftover cards from `/inventory` filtered by state='leftover'
- [x] Display freshness indicators for expiring leftovers
- [x] Refresh functionality

---

## 4) Integration: “real LLM” mode (after mock is stable)

- [x] Implement real provider in `services/api/app/core/llm_client.py` (in addition to mock)
  - [x] OpenAI integration with GPT-4/GPT-3.5 support
  - [x] Anthropic integration with Claude 3 models
  - [x] Async HTTP clients with configurable timeouts
- [x] Add env vars (API key, model, timeouts) to `services/api/.env.example`
  - [x] OPENAI_API_KEY, OPENAI_MODEL
  - [x] ANTHROPIC_API_KEY, ANTHROPIC_MODEL
  - [x] LLM_TIMEOUT configuration
- [x] Confirm:
  - [x] non-JSON rejected (handled in orchestrator with retry)
  - [x] schema invalid triggers one retry (max_retries=1 in run_task)
  - [x] failures surface `needs_clarification_questions` back to UI (status="error" or "needs_clarification")
- [x] Documentation: Created [docs/LLM_INTEGRATION.md](LLM_INTEGRATION.md) with setup guide

---

## 5) Verification (minimum before demo)

- [x] Backend contract checks
  - [x] `/plan/daily` returns schema-valid JSON
  - [x] `/plan/party` responds differently when kids are present vs all adults
  - [x] `/plan/weekly` respects `start_date` and `num_days` and includes per-day identity (backend confirmed returns 3 menus)
- [x] Mobile flow checks
  - [x] S1 → S3 → S4 → S7 works (Daily Menu → Cook Mode tested)
  - [x] S6 → party plan → S3 works (Party UI validation tested)
  - [x] S5 → weekly plan → day drill-down into S3 works (Weekly planning functional)
  - [x] Timers: user tap to start; +1 minute works; overall timer visible (all timer features tested)
  - [x] Leftovers screen working (fixed API client type issue)
- [ ] Optional final tests
  - [ ] History save on recipe completion (complete a recipe to test POST /history/recipes)
  - [ ] Test with real LLM (OpenAI/Anthropic) instead of mock

---

## 6) Release packaging (MVP)

- [ ] Configure environments (dev/stage/prod)
- [ ] Add basic logging + request IDs on backend
- [ ] Add crash reporting on mobile (optional but recommended)
- [ ] Build Android APK / iOS TestFlight

---

## Appendix: Where to implement

- Prompt pack + schemas: [docs/spec/prompt-pack.gpt-5.2.json](spec/prompt-pack.gpt-5.2.json)
- Backlog/epics: [docs/spec/engineering-plan.mvp.json](spec/engineering-plan.mvp.json)
- UI contract: [docs/spec/ui-spec.ant.figma-ready.json](spec/ui-spec.ant.figma-ready.json)
- Backend API: [services/api](../services/api)
- Flutter app: [apps/mobile](../apps/mobile)
