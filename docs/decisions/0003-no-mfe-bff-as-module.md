# ADR 0003: No MFE for MVP; optional BFF as a module

## Status
Accepted

## Context
Micro-frontends (MFE) add composition, deployment, and shared-design/versioning complexity. They are typically a web scaling pattern and are not a natural fit for a mobile-only MVP.

## Decision
- Do **not** adopt MFE for the mobile-only MVP.
- If the UI benefits from fewer round-trips and screen-shaped payloads, implement **BFF-style endpoints** as an internal module within the modular monolith (same deployable).

## Consequences
- Positive:
  - Keeps MVP simple while allowing UI-friendly API shapes
  - Preserves a clean extraction path later (BFF can become its own service if needed)
- Negative:
  - Requires discipline to keep BFF thin (no duplicated business rules)
- Follow-ups:
  - Define DTOs per screen (S1–S9) and keep them mapped to the underlying domain modules.
