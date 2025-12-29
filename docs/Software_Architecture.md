# SAVO — Production-Ready Software Architecture (MVP → Scale)

This architecture is aligned to SAVO’s core design:
- **Single MVP**
- **UI-first**
- **API-driven**
- **AI-orchestrated**
- **Global/cuisine-agnostic**
- **Single primary model** (GPT-5.2) for 90% of reasoning

## Architectural style
**UI-first, API-driven, AI-orchestrated modular monolith (MVP)**.

MVP scope decision:
- **Primary client is mobile-only**.
- Micro-frontends (MFE) are not a target architecture for this MVP.

Rationale for MVP:
- Faster delivery and iteration
- Lower operational overhead and cost
- Easier debugging and end-to-end tracing
- Clear migration path to microservices later (only when needed)

## High-level reference architecture
```text
┌──────────────────────────────┐
│        Mobile / Web UI       │
│   (iOS / Android / Web)      │
└──────────────┬───────────────┘
               │ HTTPS (JSON)
┌──────────────▼───────────────┐
│          API Gateway         │
│ Auth • Rate Limit • Routing  │
└──────────────┬───────────────┘
               │
┌──────────────▼───────────────┐
│     Backend Orchestrator      │
│  (Node.js / Python)           │
│  - Session logic              │
│  - Cuisine metadata           │
│  - Scaling & rules            │
│  - Feature flags              │
└──────────────┬───────────────┘
               │
┌──────────────▼───────────────┐
│   AI Orchestration Layer      │
│     (Prompt Builder)          │
│  - Task routing               │
│  - Schema binding             │
│  - Retry & correction         │
└──────────────┬───────────────┘
               │
┌──────────────▼───────────────┐
│        LLM (GPT-5.2)          │
└──────────────┬───────────────┘
               │
┌──────────────▼───────────────┐
│     Validation & Guards       │
│  - Schema validation          │
│  - Safety & diet checks       │
│  - Hallucination guard        │
└──────────────┬───────────────┘
               │
┌──────────────▼───────────────┐
│        Persistence Layer      │
│  Postgres • Redis • Object    │
└──────────────────────────────┘
```

## Layer responsibilities
### 1) Frontend (UI-first)
Recommended: React Native for iOS/Android.

Responsibilities:
- Collect user input (config, inventory, session intent)
- Render AI outputs (menus, recipes, cook steps)
- Provide cook mode UX (stepper, timers, tips)

Non-responsibilities:
- No domain rules (scaling/variety/allergens) beyond basic input validation
- No LLM prompts in the client

### 2) API Gateway
Responsibilities:
- Authentication/authorization (JWT/OAuth)
- Rate limiting
- Request/response logging and correlation IDs

Can be:
- Cloud gateway (AWS/GCP/Azure) or in-app middleware for early MVP

Optional (mobile-only): **BFF-style routes**
- If the mobile UI benefits from aggregated/screen-shaped payloads, implement a “mobile BFF” as a thin routing/DTO layer inside the same deployable (still a modular monolith).

### 3) Backend Orchestrator (the “brain”)
This is the core application service and should own all state and domain rules.

Responsibilities:
- Load **persistent configuration** (household, diets, units, behaviors)
- Load **inventory** and freshness/leftover state
- Load **cuisine metadata** (structures + templates)
- Apply deterministic rules:
  - servings/scaling
  - avoid repetition window
  - expiring-first bias
  - leftover reuse scheduling
- Build the prompt context for the AI orchestration layer
- Persist validated results and user choices

### 4) AI Orchestration (prompt builder)
This is not the LLM. It is the reliability layer that makes LLM outputs predictable.

Responsibilities:
- Task routing using the prompt pack (normalize, plan daily/party/weekly, YouTube rank)
- Persona selection (beginner/expert/kid-friendly)
- JSON schema enforcement (reject non-JSON)
- Retry-on-invalid-json (max 1) with correction instructions

Source of truth: `docs/spec/prompt-pack.gpt-5.2.json`

### 5) LLM (GPT-5.2)
Role:
- Generates menus, recipes, quantities, steps, nutrition estimates, and summaries

Key rule:
- The model is stateless; it does not store user state.
- All state comes from and is saved by the backend.

### 6) Validation & guardrails
Responsibilities:
- Validate responses with JSON Schema (fail closed)
- Enforce constraints:
  - diet/allergen/health
  - ingredient availability (no hallucinated inventory IDs)
  - time feasibility
  - sensible calorie/macros bounds
- If constraints cannot be satisfied, return `status=needs_clarification` with questions

### 7) Persistence
- **Postgres**: source of truth (users/households, config, inventory, cuisines, history, plans)
- **Redis**: caching and fast lookups (recent history window, cuisine metadata cache, rate limits)
- **Object storage**: transcripts, media, generated assets (optional in MVP)

## End-to-end flows
### “Cook Today”
1. UI calls `POST /plan/daily`
2. Orchestrator loads config + inventory + cuisine metadata + history
3. Orchestrator applies deterministic rules (servings, repetition, expiring-first)
4. AI orchestration calls GPT-5.2 using `TASK_PLAN_DAILY_MENU`
5. Validation layer schema-validates + enforces rules
6. Persist plan + return `MENU_PLAN_SCHEMA` to UI

### “Start Cooking”
1. UI opens Cook Mode for a selected recipe option
2. UI tracks step progress and timers locally
3. UI posts completion to `POST /history/recipes` (and leftover hints)
4. Backend updates history + leftovers center

## External integrations (MVP-friendly)
- **YouTube**: rank candidates + summarize transcript (cache results)
- **Nutrition sources (optional)**: validate estimates (not mandatory for MVP)

## Why this is the best choice
- Keeps AI predictable: prompts are centralized and schema-validated
- Keeps product flexible: cuisines/structures are metadata-driven
- Keeps costs controlled: single model, caching, retry cap
- Keeps scale easy: split components only when pressure appears (traffic/latency/org)

## Scalability path (future)
When needed, evolve by extraction:
- Move AI orchestration to its own service
- Add background jobs (nightly weekly planning; transcript ingestion)
- Add vector DB for preference/taste memory (optional)
- Add B2B SmartChef integrations via separate integration service

No rewrite required; extraction follows clear module boundaries.
