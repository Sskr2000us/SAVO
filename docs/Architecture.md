# Architecture — SAVO / SmartChef

For the full production-ready reference architecture (layers, responsibilities, flows, scaling path), see `docs/Software_Architecture.md`.

## 1. Guiding principles
- Reliability > novelty
- Local-first where possible; cloud-assisted where valuable
- Observable sessions: every cook is an auditable event stream

## 1.1 Architectural style (MVP)
**UI-first, API-driven, AI-orchestrated modular monolith**.
This keeps MVP delivery fast and debuggable while preserving a clean path to microservices later.

## 2. Conceptual components
- **Client app**: selects recipe, starts a session, shows step guidance
- **Session engine (SmartChef Core)**: deterministic step progression with timers and sensor gates
- **Device adapters**: normalized interface for ovens/thermometers
- **Data store**: recipes + sessions + device registry
- **Optional cloud**: account sync, recipe catalog, analytics

## 2.1 AI orchestration pattern (MVP)
Everything routes through a single LLM endpoint (primary model) with schema + rule validation.

```text
┌──────────────────────────────┐
│        Mobile / Web UI       │
└──────────────┬───────────────┘
			   │ HTTPS (JSON)
┌──────────────▼───────────────┐
│        API Gateway            │
│  Auth • Rate Limit • Routing  │
└──────────────┬───────────────┘
			   │
┌──────────────▼───────────────┐
│     Backend Orchestrator      │
│  (Node.js / Python)           │
│  - Session logic              │
│  - Cuisine metadata           │
│  - Scaling & rules            │
└──────────────┬───────────────┘
			   │
 ┌─────────────▼─────────────┐
 │     Prompt Builder Layer   │
 │  - GPT-5.2 prompts         │
 │  - JSON schema enforcement │
 │  - Retry & correction      │
 └─────────────┬─────────────┘
			   │
 ┌─────────────▼─────────────┐
 │        LLM (GPT-5.2)       │
 └─────────────┬─────────────┘
			   │
 ┌─────────────▼─────────────┐
 │     Validation & Guards    │
 │  - Schema validation       │
 │  - Safety & diet checks    │
 │  - Hallucination guard     │
 └─────────────┬─────────────┘
			   │
┌──────────────▼───────────────┐
│        Persistence Layer      │
│  Postgres • Redis • Object    │
└──────────────────────────────┘
```

## 3. Data flow (high level)
1. User starts a cooking session for a recipe
2. Session engine emits “current step” + next actions
3. Device adapter streams sensor/device state updates
4. Session engine advances steps based on time or sensor conditions

## 3.1 JSON as the integration contract
SAVO uses a versioned “feed” object as the contract between UI ↔ orchestrator ↔ LLM.
See `docs/spec/` for:
- Example feed (build-ready)
- JSON Schema for validation

## 3.2 Core flows (MVP)
### Cook Today
UI → `POST /plan/daily` → orchestrator loads config/inventory/metadata/history → prompt builder calls GPT-5.2 → validate → persist → return plan JSON.

### Start Cooking
UI runs cook mode stepper/timers → completion logged to backend → history + leftovers updated.

## 4. Interfaces (to formalize)
- Recipe model
- Session state machine
- Device state model (temp, connectivity, mode)

## 5. Deployment options (choose one)
- A) App-only (manual timers)
- B) App + local hub (LAN service)
- C) App + cloud API + optional local device bridge

## 6. Risks
- Device integration complexity and variability
- Safety implications (temperature guidance, food handling)
- Connectivity and pairing UX



