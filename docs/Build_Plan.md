# Build Plan — SAVO MVP (based on JSON specs)

This plan maps directly to:
- `docs/spec/prompt-pack.gpt-5.2.json`
- `docs/spec/engineering-plan.mvp.json`
- `docs/spec/ui-spec.ant.figma-ready.json`

## 1) What we are building (MVP contract)
### Product pipeline
1. **Persistent app configuration** (household profile + preferences)
2. **Session intent** (today / party / weekly / leftovers)
3. **Cuisine metadata** (10 cuisines; drives course headers)
4. **AI generation** (menus → recipes → steps → nutrition → leftovers → YouTube refs)

### Core MVP user journeys
- S1 → S3 → S4 → S7 (Cook Today)
- S2 → S3 (inventory-driven plan)
- S6 → S3 (Party plan)
- S5 (Weekly plan)
- S8 (Leftovers hub)
- S9 (Settings)

## 2) System architecture plan (matches your diagram)
### Services (logical)
- **API Gateway**: auth, rate limiting, routing
- **Backend Orchestrator**: session logic, cuisine metadata, scaling rules
- **Prompt Builder**: builds GPT-5.2 requests using prompt pack task templates
- **Validation & Guards**:
  - JSON-schema validation (fail closed)
  - rule checks (allergens, time budget, ingredient constraints)
  - retry-on-invalid-json (max 1) with “fix your JSON” instruction
- **Persistence**:
  - Postgres: users/households, inventory, cuisine metadata, history
  - Redis: caching cuisine metadata, recent history windows, plan results
  - Object storage (optional): media, recipe images, cached transcripts

### API shape (minimal)
- `POST /auth/*` (if using accounts; optional for early prototype)
- `GET/PUT /config` — persistent `app_configuration`
- `GET/POST/PUT/DELETE /inventory` — raw inventory
- `POST /inventory/normalize` — returns `NORMALIZATION_OUTPUT_SCHEMA`
- `GET /cuisines` — returns cuisine list + structures
- `POST /plan/daily` — returns `MENU_PLAN_SCHEMA`
- `POST /plan/party` — returns `MENU_PLAN_SCHEMA`
- `POST /plan/weekly` — returns `MENU_PLAN_SCHEMA` (menus contain `weekly_day`)
- `POST /youtube/rank` — returns `YOUTUBE_RANK_SCHEMA`
- `POST /history/recipes` (log completion + selected recipes)

## 3) Data model plan (first version)
### Postgres tables (suggested)
- `households`, `members`
- `app_configuration` (1 per household)
- `inventory_items` (quantity/unit/state/storage/freshness)
- `canonical_ingredients` (id, canonical_name, synonyms)
- `cuisine_metadata` (10 cuisines + daily/party structures)
- `plan_requests`, `plan_responses` (store validated JSON + scores)
- `cook_history` (recipe_id, cuisine, method, timestamp, ratings)
- `youtube_cache` (video_id, transcript hash, summary, trust_score)

### Variety rules storage
- Keep a rolling window in Redis (e.g., last N recipes/cuisines/methods) to implement `avoid_repetition_days` and diversity scoring.

## 4) AI implementation plan (prompt pack → runtime)
### How each prompt task becomes code
- `TASK_NORMALIZE_INVENTORY` → `/inventory/normalize`
  - Input: raw inventory + staples policy
  - Output: normalized items + applied staples policy

- `TASK_PLAN_DAILY_MENU` → `/plan/daily`
  - Input bindings: config + session_request + normalized inventory + cuisine metadata + history
  - Output: `MENU_PLAN_SCHEMA`

- `TASK_PLAN_PARTY_MENU` → `/plan/party`
  - Add `party_settings` guest count, 10% buffer, sequencing guidance

- `TASK_PLAN_WEEKLY` → `/plan/weekly`
  - Returns 7 “weekly_day” menus; enforce max repeats and leftover scheduling

- `TASK_YOUTUBE_RANK` → `/youtube/rank`
  - Ranks candidates + returns reasons

### Guardrails (MVP minimum)
- **Schema-first**: validate every LLM response against the referenced schema.
- **Ingredient non-hallucination**: enforce that `ingredients_used[*].inventory_id` exists in inventory; optional ingredients must be explicitly flagged as `new_ingredients_optional`.
- **Diet/allergen checks**: rule engine runs after generation; if violated, return `needs_clarification` or regenerate with constraints.
- **Time feasibility**: sum `estimated_times.total_minutes` and per-step times; reject if exceeds `time_available_minutes`.

## 5) Engineering execution plan (by sprint)
This follows the `release_plan.recommended_sprints` in `engineering-plan.mvp.json`.

### Sprint 1 — Foundations (E1 + E2-S1 + E3-S1)
- UI: S9 Settings (config), S2 Inventory, S1 Home shell
- Backend: config CRUD, inventory CRUD, cuisine metadata store + `GET /cuisines`
- Acceptance: users can set config, manage inventory, browse cuisines

### Sprint 2 — Planning engine (E2-S2 + E4-S1 + E8-S1)
- Backend: orchestrator + prompt builder + schema validator
- Build `/inventory/normalize` + `/plan/daily` end-to-end
- UI: S3 Plan Results consumes `MENU_PLAN_SCHEMA`
- Acceptance: daily plan produces 2–3 options per course, headers from cuisine metadata

### Sprint 3 — Cook mode + leftovers (E5-S1 + E6-S1)
- UI: S4 Recipe Detail, S7 Cook Mode, S8 Leftovers Center
- Backend: save history on completion + derive leftovers hub entries
- Acceptance: cook session completes + logs history + populates leftovers center

### Sprint 4 — YouTube + telemetry + polish (E7-S1 + E8-S2)
- Backend: YouTube ranking + transcript summarization cache
- Observability: latency/cost/success rate dashboards; store diversity + selection
- UI: YouTube 60-sec summary module in S4
- Acceptance: top videos + summaries appear; metrics collected per request

## 6) Build order checklist (practical)
1. Lock the **master request object** shape (config + intent + inventory + cuisine metadata + history)
2. Implement **schema validation library** (fail closed)
3. Implement `/inventory/normalize` and get stable canonical IDs
4. Implement `/plan/daily` with strict bindings + “retry once” policy
5. Wire S3 UI to show results exactly as schema returns
6. Add cook history + repetition window enforcement
7. Add party/weekly once daily is stable

## 7) Open choices (you can decide later, but they affect scaffolding)
- Frontend (mobile-only): React Native vs Flutter
- Backend: Node (Nest/Express) vs Python (FastAPI)
- Auth: anonymous-first (device-bound) vs account-first
- YouTube: live search vs pre-indexed curated set

Notes:
- Micro-frontends (MFE) are out-of-scope for mobile-only MVP.
- A BFF can be implemented as an internal module in the modular monolith if the mobile UI needs aggregated, screen-shaped endpoints.

If you tell me your preferred stack (RN+Node or Flutter+FastAPI), I can scaffold the actual backend orchestrator + validator and the mobile UI shell next.
