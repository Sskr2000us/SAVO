# PRD — SAVO (Smart home cooking, powered by SmartChef)

## 0. MVP flow (system contract)
SAVO MVP is organized as a deterministic pipeline:

1. **App configuration (persistent)**
  - User/household profile, dietary rules, unit preferences, safety boundaries, feature flags
2. **Session intent (per request)**
  - “today” / “party” / “leftovers” / “weekly plan” plus servings, time budget, constraints
3. **Cuisine metadata (drives structure)**
  - Cuisine templates, pantry staples, typical sequencing, equipment assumptions
4. **AI generation**
  - Recipes, quantities, scaling, guidance, shopping list, nutrition estimates, leftover reuse plan

This pipeline is represented by a single JSON feed (see `docs/spec/`).

## 1. Summary
SAVO helps home cooks reliably produce great results by combining guided cooking workflows with real-time appliance/temperature feedback.

## 2. Problem
Home cooking is error-prone due to timing uncertainty, inconsistent heat, multi-dish coordination, and lack of feedback from appliances.

## 3. Goals
- Increase cooking success rate for common meals
- Reduce cognitive load during cooking
- Provide clear, actionable guidance based on live signals (time/temperature/device state)

## 4. Non-goals (initial)
- Restaurant-grade menu planning
- Social/community recipe sharing (unless explicitly required)
- Full nutrition tracking

## 5. Target users
- Busy home cooks who want reliability
- Beginners who need step-by-step guidance
- Enthusiasts who want repeatability and device integration

## 6. Core use cases
1. Guided cook: user selects recipe → system guides steps → monitors temperature/device status
2. Doneness-driven cooking: probes/thermometers drive step transitions
3. Multi-stage workflow: prep → cook → rest → serve reminders

## 7. Key product requirements (MVP)
- Recipe model with steps, timers, and optional sensor gates (e.g., “advance when internal temp >= X”)
- Session model that tracks progress through steps
- Persistent configuration model (household, diets/allergens, units, safety thresholds, feature flags)
- Intent-driven planning modes:
  - Today (single meal)
  - Party (multi-dish, scaled servings)
  - Leftovers (reuse + reduce waste)
  - Weekly planning (simple plan + shopping list)
- Integrations (choose at least one for MVP):
  - Smart thermometer (BLE/Wi‑Fi)
  - Smart oven
  - Manual mode (no device), timers only

## 8. AI orchestration requirements (MVP)
### 8.1 Primary model strategy
Use **one primary model** for the majority of reasoning and JSON generation:
- **GPT-5.2**: recipe generation, menu planning, scaling, leftovers, multilingual instructions, YouTube step summaries, agent dialogue, JSON schema output

### 8.2 Optional specialist models (later)
- Vision ingredient scanning (optional): image-to-inventory extraction (e.g., fridge/pantry)
- Safety / hallucination guard (optional advanced): post-generation constraint validation (can be rule-based for MVP)

### 8.3 Required safeguards (MVP)
- Strict JSON schema enforcement (validate + retry with correction)
- Rule validation (diet/allergen constraints, time budget, serving scaling sanity)
- Safety disclaimers and hard boundaries (e.g., “do not provide medical advice”)

## 9. Success metrics
- % of sessions completed
- User-reported outcome rating
- Time-to-first-successful-cook
- Reduction in “panic moments” (user interrupts, restarts, abandons)

## 10. Constraints & assumptions
- Must work offline or in degraded connectivity (define scope)
- Safety: guidance must avoid unsafe temperatures/handling (define boundaries)

## 11. Open questions
- Primary surface: **mobile-only** (MVP)
- Supported devices for MVP
- Local-first vs cloud-first

## 12. Deliverable artifact (for implementation)
- A single, comprehensive JSON feed representing config + intent + metadata + generation output
- A versioned JSON Schema for validation


