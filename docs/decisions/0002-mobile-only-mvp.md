# ADR 0002: Mobile-only MVP

## Status
Accepted

## Context
SAVO’s MVP is UI-first and needs rapid iteration with minimal surface-area and operational complexity.

## Decision
SAVO MVP will be **mobile-only**.

## Consequences
- Positive:
  - Faster delivery (single client implementation)
  - Simpler authentication/session handling
  - Less fragmentation in UX and API shape
- Negative:
  - No first-class web experience in MVP
- Follow-ups:
  - If web becomes a requirement, introduce it as a separate client later and consider a dedicated web BFF only if needed.
