# UI ↔ Backend End-to-End Audit (SAVO)

Date: 2026-01-04

This audit focuses on: (1) backend endpoints that exist but are not reachable from UI, (2) UI screens/buttons that are not wired to backend, and (3) rollout controls (country/market feature flags).

## Backend Route Groups (FastAPI)

Source: `services/api/app/api/router.py`

- `/plan/*` (planning)
  - UI usage: YES (Daily / Weekly / Party planners)
- `/inventory/*` (inventory summaries)
  - UI usage: YES (inventory preview + leftovers screens)
- `/inventory-db/*` (CRUD + deduct)
  - UI usage: YES (inventory CRUD + cook mode deduct)
- `/api/scanning/*` (vision scanning)
  - UI usage: YES (scan/confirm/history/pantry/check-sufficiency)
- `/recipes/*` (recipe import)
  - UI usage: YES (`/recipes/import`, `/recipes/import/image`)
- `/youtube/*` (search/rank/summary)
  - UI usage: YES
- `/profile/*` (household + family members + onboarding)
  - UI usage: YES (onboarding + settings)
- `/security/*` (session/device security)
  - UI usage: PARTIAL
  - Notes: backend endpoints exist; some UI is “simulated” or incomplete.
- `/history/*` (history)
  - UI usage: NO (no obvious navigation entrypoints)
- `/nutrition/*` (nutrition)
  - UI usage: NO (no obvious navigation entrypoints)
- `/training/*` (training)
  - UI usage: NO
- `/cuisines/*` (cuisine catalog)
  - UI usage: NO
- `/config` (app config)
  - UI usage: NO (currently storage-backed, not profile-backed)

## High-Impact Gaps (what users feel as “missing features”)

1) **Feature rollout control (country/market)**
- Problem: the app cannot hide/show features by market, and there’s no admin UI.
- Fix shipped: `/market/config` + admin endpoints + Flutter gating.

2) **Security device/session management**
- Backend: `/security/sessions`, `/security/events`, revoke endpoints exist.
- UI: there are settings screens that mention “simulate”/not fully wired.
- Next: wire Settings → Security screens to these endpoints and surface events.

3) **History / Nutrition / Training**
- Backend route groups exist but no UI entrypoints are visible.
- Next: add simple screens or integrate into existing flows (Plan/Cook/Settings) once product requirements are clear.

## Rollout & Admin Controls (new)

Backend:
- `GET /market/config` returns region-scoped flags for the current user.
- `PUT /admin/market/feature-flags` (super admin only)
- `PUT /admin/market/retailers` (super admin only)

Flutter:
- Loads market config at startup.
- Gates Shopping List visibility (can be disabled for a region).
- Adds an Admin screen in Settings for super admins.

## Notes / Risks

- Admin authentication currently supports env allowlist (`SUPER_ADMIN_EMAILS` / `SUPER_ADMIN_USER_IDS`) and optional DB column `users.is_super_admin`.
- JWT validation in backend middleware is currently bypassed (`verify_signature=False`). This is a security risk; admin endpoints assume you will tighten auth before production.
