# Vector Schema + Query Examples (Ingredients / Pantry / Recipes / Intents)

Vector layer goal: conceptual search and recommendations. It is gated by feature flags and entry thresholds.

## Core rule
Vector updates are **event-driven only**. Cron jobs are explicitly disallowed.

## Entity schemas
All vector objects share:
- `id`: stable identifier
- `namespace`: logical partition (e.g. `user:<uuid>`)
- `embedding_version`: explicit version string
- `provider`: embedding provider name
- `text`: canonical text used to generate embeddings
- `metadata`: structured fields for filters

### 1) Ingredient
- `id`: `ingredient:<ingredient_id>` or `ingredient:<canonical_name>`
- `text`: canonical ingredient name + synonyms
- `metadata`:
  - `canonical_name`
  - `taxonomy_version`
  - `cuisine_tags` (optional)

Example:
```json
{
  "id": "ingredient:tomato",
  "namespace": "global",
  "embedding_version": "v0",
  "provider": "noop",
  "text": "tomato (solanum lycopersicum) fresh, canned",
  "metadata": {
    "canonical_name": "tomato",
    "taxonomy_version": "2026-01-10"
  }
}
```

### 2) Pantry state
Represents a user’s pantry snapshot or an item state.
- `id`: `pantry_item:<inventory_item_id>`
- `namespace`: `user:<uuid>`
- `text`: `canonical_name` + state cues (`fresh`, `low stock`, etc.)
- `metadata`:
  - `storage_location`, `item_state`, `pantry_status`
  - `is_current`
  - `updated_at`

### 3) Recipe
- `id`: `recipe:<recipe_id>`
- `namespace`: `global` or `user:<uuid>`
- `text`: recipe title + ingredients + cuisine + technique
- `metadata`:
  - `cuisine`
  - `dietary_tags`
  - `servings`

### 4) Cooking intent
- `id`: `intent:<slug>`
- `namespace`: `global`
- `text`: intent description (e.g. “quick high-protein dinner under 20 minutes”)
- `metadata`:
  - `time_budget_minutes`
  - `constraints` (vegetarian, allergy-safe, etc.)

## Query examples

### A) Semantic food search
Goal: “Something like paneer but vegan”.
1) Embed query text.
2) Query ingredient namespace.

Pseudo:
```python
emb = embed("something like paneer but vegan")
results = vector.query(namespace="global", embedding=emb, top_k=10)
```

### B) Substitution reasoning
Goal: recommend substitutes for missing ingredients.
- Query ingredient embedding near the missing ingredient.
- Filter by dietary constraints.

Pseudo:
```python
emb = embed("paneer")
results = vector.query(namespace="global", embedding=emb, top_k=10, filters={"dietary": "vegan"})
```

### C) Cuisine affinity
Goal: suggest recipes that match user’s historical cuisine preference.
- Build a user cuisine preference vector from recipe interactions (event-driven).
- Query recipes by similarity.

### D) Intent-based recommendations
Goal: “high-protein breakfast”.
- Embed intent text.
- Query recipes.

## Integration notes
- Always bump `embedding_version` when changing prompt/text format or provider.
- Store `taxonomy_version` with ingredient and observation-derived embeddings.
- When vector flags/thresholds aren’t met, fall back to non-vector search paths.
