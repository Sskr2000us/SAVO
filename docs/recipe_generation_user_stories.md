# SAVO Recipe Generation — User Stories

Design goal: trustworthy, pantry-aware, vector-powered recipe intelligence.

Core rule: **Recipes are generated from constraints, not imagination.**

## Definitions
- **Pantry truth**: the canonical current state of the pantry (not raw observations).
- **Modes**:
  - **Retrieved**: curated/licensed recipes; ranked by vector similarity + pantry coverage.
  - **Assembled**: deterministic assembly via ingredient sets + techniques + cuisine rules.
  - **Generated**: LLM output allowed only after constraints are locked; LLM fills structure only.
- **Distribution target**: retrieved+assembled >= 80%; generated <= 20%.

## Canonical recipe schema (acceptance contract)
A recipe response must conform to:
- `recipe_id` (uuid)
- `recipe_name` (string)
- `cuisine` (string)
- `dietary_tags` (string[])
- `prep_time_minutes` (number)
- `difficulty` (easy|medium|hard)
- `ingredients[]`:
  - `ingredient_id` (uuid)
  - `quantity` (number)
  - `unit` (string)
  - `optional` (boolean)
- `techniques` (string[])
- `steps` (string[])
- `serves` (number)
- `created_from` (retrieved|assembled|generated)
- `version` (e.g. `v1`)

## Epic A — Intent Resolution (constraints-first)

### Story A1 — Resolve user intent into structured constraints
As a user, I want my request (e.g. “quick dinner, feels Italian, use expiring items”) translated into explicit constraints so that the recipe is grounded and predictable.
- Acceptance criteria:
  - Output includes: cuisine, max_time_minutes, dietary tags, preference hints, and “use expiring items” flag.
  - If user input is ambiguous, system chooses the simplest interpretation and records assumptions.

### Story A2 — Preserve the locked constraints for auditability
As the system, I want the final constraint set to be locked and stored before any generation so that later outputs can be explained and replayed.
- Acceptance criteria:
  - A “locked constraints” object exists for every recipe attempt.
  - Any later changes create a new constraints version (no in-place overwrite).

## Epic B — Pantry Coverage & Missing Items (trustworthy grounding)

### Story B1 — Compute pantry coverage against pantry truth
As a user, I want SAVO to prefer recipes I can actually cook with what I have so that suggestions feel reliable.
- Acceptance criteria:
  - Coverage % computed from pantry truth and candidate recipe ingredients.
  - Coverage threshold logic supports preferred match threshold (>= 70%).

### Story B2 — Explicitly label missing ingredients
As a user, I want missing ingredients clearly labeled (not silently assumed) so that I can decide what to buy.
- Acceptance criteria:
  - Any ingredient not available in pantry truth is marked as missing (or optional if allowed by recipe definition).
  - No recipe claims to “use what you have” if it requires missing ingredients beyond allowed policy.

## Epic C — Mode Selection (retrieve → assemble → generate)

### Story C1 — Select retrieve/assemble/generate based on policy
As the system, I want a deterministic path selection with an explicit reason so that the process is auditable.
- Acceptance criteria:
  - For each recipe attempt, the system records `path` and `reason` (pantry_match|novelty|personalization).
  - Generated path is only selected when retrieved+assembled cannot satisfy locked constraints.

### Story C2 — Enforce distribution target (generated <= 20%)
As a product owner, I want generation to be the exception so that cost and trust are controlled.
- Acceptance criteria:
  - System tracks mode distribution over time.
  - If generated mode exceeds 20% over a rolling window, system increases retrieval/assembly preference or tightens generation entry conditions.

## Epic D — Retrieved Recipes (curated/licensed)

### Story D1 — Retrieve recipes by constraints
As a user, I want retrieved recipes that match cuisine, dietary rules, and time so that results feel relevant.
- Acceptance criteria:
  - Retrieval filters enforce hard constraints before ranking.
  - Returned recipes always conform to canonical schema.

### Story D2 — Rank retrieved recipes using vector + pantry coverage
As a user, I want retrieved recipes ranked by conceptual match and pantry fit so that top results are both appealing and cookable.
- Acceptance criteria:
  - Ranking inputs include vector similarity and pantry coverage.
  - Ranking factors can incorporate expiry urgency, cuisine affinity, past acceptance, simplicity score.

## Epic E — Assembled Recipes (deterministic construction)

### Story E1 — Assemble recipe deterministically from cuisine rules
As a user, I want assembled recipes to follow cuisine logic so that they feel authentic and repeatable.
- Acceptance criteria:
  - Given the same locked constraints + pantry truth snapshot, assembly output is deterministic.
  - Techniques and ingredient sets come from explicit rules/lookup tables (not LLM creativity).

### Story E2 — Preserve “why these ingredients” trace
As a user, I want to understand why an ingredient is included so that I can trust the recipe and modify it.
- Acceptance criteria:
  - Each assembled ingredient is explainable via a rule reference (e.g. “Italian base: garlic + olive oil”).

## Epic F — Constrained Generation (LLM fills structure only)

### Story F1 — Build a constrained prompt from locked constraints
As the system, I want an LLM prompt that includes only approved constraints so that the LLM cannot invent requirements.
- Acceptance criteria:
  - Prompt includes cuisine, allowed ingredients list, allowed techniques, max_time_minutes, dietary tags.
  - Prompt requires output in canonical schema.

### Story F2 — Prevent the LLM from deciding constraints
As a product owner, I want constraints to be decided outside the LLM so that outputs are safe and repeatable.
- Acceptance criteria:
  - The LLM input contains a locked constraints block and instructions to not modify it.
  - The system rejects outputs that contradict hard constraints.

### Story F3 — Validate generated output against hard constraints
As the system, I want a strict validator so that generated recipes never violate pantry/dietary/time rules.
- Acceptance criteria:
  - Validator checks:
    - pantry-only or explicitly missing ingredients
    - cuisine logic required fields present
    - dietary enforcement
    - max cooking/prep time respected
  - If validation fails: do not show recipe; either retry with tighter prompt or fall back to retrieve/assemble.

## Epic G — UX Trust Signals (trust over novelty)

### Story G1 — Show required trust signals on every recipe
As a user, I want clear trust indicators so that I can quickly judge if the recipe is realistic.
- Acceptance criteria (must display):
  - “uses what you have” (only if coverage policy satisfied)
  - estimated time
  - “uses expiring items” (if applicable)
  - adjustable spice level

### Story G2 — Never hide dietary violations
As a user, I want dietary issues to be blocked upfront so that I’m safe.
- Acceptance criteria:
  - If dietary constraints cannot be satisfied, no recipe is returned; user is prompted to adjust constraints.

## Epic H — Vector-Powered Ranking (intelligence layer)

### Story H1 — Use vector intelligence for ranking, not imagination
As the system, I want vector similarity to influence ranking so that recommendations reflect meaning and preference.
- Acceptance criteria:
  - Vector signals are applied only in ranking/re-ranking.
  - If vector is disabled/unavailable, system falls back to non-vector ranking.

### Story H2 — Gate vector features behind flags and thresholds
As an operator, I want vector features to activate only when thresholds are met so that small deployments remain simple.
- Acceptance criteria:
  - Feature flags control vector usage.
  - Thresholds for minimum pantry items and/or recipe corpus size are enforced.

## Epic I — Feedback + Learning Loop (compounding)

### Story I1 — Capture recipe feedback events
As the system, I want to capture feedback events so that ranking improves over time.
- Acceptance criteria:
  - Emit events: `recipe.accepted`, `recipe.modified`, `recipe.rejected`.
  - Store signals: cooked/skipped, step edits, ingredient substitutions, time adjustments.

### Story I2 — Feed feedback into re-ranking
As a user, I want SAVO to improve based on what I accept or reject so that suggestions get better.
- Acceptance criteria:
  - Feedback updates a user taste model and influences ranking factors (past acceptance, cuisine affinity).
  - Learning does not mutate history; new signals are appended.

## Epic J — Safety and Quality Guardrails

### Story J1 — Never generate unsafe instructions
As a user, I want SAVO to avoid unsafe cooking instructions so that I’m not harmed.
- Acceptance criteria:
  - Unsafe instruction patterns are blocked.
  - When blocked, system returns a safe alternative or refuses with a clear reason.

### Story J2 — Never claim unavailable ingredients are present
As a user, I want ingredient availability to be truthful so that I don’t waste time.
- Acceptance criteria:
  - Ingredients not in pantry truth must be explicitly labeled missing.
  - Generated recipes cannot introduce new ingredients outside allowed set.

### Story J3 — Always allow user edits
As a user, I want to edit steps and ingredients so that I stay in control.
- Acceptance criteria:
  - User edits are permitted even if they reduce pantry coverage.
  - The system updates trust signals accordingly (e.g., coverage drops).

## Epic K — End-to-End Flow

### Story K1 — Run the full pipeline from scan to recipe
As a user, I want the full flow (scan → pantry truth → vector → retrieval/assembly → constrained generation → feedback) to work as one system.
- Acceptance criteria:
  - Pantry truth is the source of ingredient availability.
  - Mode selection is recorded; output conforms to canonical schema.
  - Feedback events are emitted for acceptance/modification/rejection.
