# V1 → V2 Migration Checklist (Repeatable + Auditable)

Scope: Supabase/Postgres schema + FastAPI control-plane flags.

## 1) Freeze (V1 Contract)
- [ ] Confirm `services/api/migrations/028_freeze_v1_contracts.sql` applied
- [ ] Confirm CI guard passes: `python scripts/check_v1_contracts_immutable.py`
- [ ] Confirm no new writes to any `*_v1` tables (DB enforced)

## 2) Side-by-side Schema
- [ ] Apply `services/api/migrations/029_side_by_side_versioned_schemas.sql`
- [ ] Verify RLS + views exist:
  - `public.pantry_items_v1`, `public.pantry_items_v2`
  - `public.scan_observations_v1`, `public.scan_observations_v2`

## 3) Dual-write Window
- [ ] Set `SAVO_SCHEMA_MIGRATION_MODE=dual_write`
- [ ] Set bounded window:
  - `SAVO_SCHEMA_MIGRATION_WINDOW_START=<iso>`
  - `SAVO_SCHEMA_MIGRATION_WINDOW_END=<iso>`
- [ ] Verify inventory writes are mirrored best-effort and failures emit `migration.incident`

## 4) Shadow Validation
- [ ] Set `SAVO_ENABLE_V2_SHADOW_READ=true`
- [ ] Trigger `POST /api/migration/run-shadow-validation`
- [ ] Review:
  - `GET /api/migration/reports?event_type=schema.v2_shadow_report`
  - `GET /api/migration/metrics`

## 5) Phased Cutover (Progressive Reads)
- [ ] Enable progressive reads: `SAVO_ENABLE_PROGRESSIVE_V2_READS=true`
- [ ] Internal phase:
  - `SAVO_ROLLOUT_PHASE=internal`
  - `SAVO_INTERNAL_USER_ALLOWLIST=<comma-separated user ids>`
- [ ] Expand rollout:
  - `SAVO_ROLLOUT_PHASE=1%` → `10%` → `100%`
- [ ] Emergency rollback available at all times:
  - `SAVO_FORCE_READ_V1=true`

## 6) Cutover (V2 Truth)
- [ ] Set `SAVO_SCHEMA_MIGRATION_MODE=v2_only`
- [ ] Disable V1 writes (belt + suspenders): `SAVO_DISABLE_V1_WRITES=true`
- [ ] Confirm:
  - V2 is the truth source for reads
  - V2 receives all writes
  - V1 remains readable for audit/replay

## 7) Deprecation (No Deletes; Replayable)
- [ ] Apply append-only constraints:
  - `services/api/migrations/030_append_only_v2_observations.sql`
- [ ] Apply required version enforcement + quarantine:
  - `services/api/migrations/031_required_versions_and_quarantine.sql`
- [ ] Verify replay outputs tables:
  - `services/api/migrations/032_replay_outputs.sql`
- [ ] Run a replay dry-run:
  - `python scripts/replay_event_log.py --user-id <uuid> --from-ts <iso> --to-ts <iso>`

## 8) Post-cutover Monitoring
- [ ] Watch for regressions:
  - latency (`api.latency`) via `GET /api/migration/metrics`
  - mismatch rate (`schema.v2_shadow_report`) via `GET /api/migration/metrics`
  - incidents (`migration.incident`) via `GET /api/migration/metrics`
