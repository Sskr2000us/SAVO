# SAVO V1 Contracts (Frozen)

## Purpose
This document defines the **frozen V1 contract baseline**. V1 is treated as an **immutable compatibility target**.

**Core principle:** Never migrate data. Migrate interpretation.

Operational stance:
- Deletion is technical debt; deprecation is maturity.
- V1 stays readable for audit/replay, but becomes write-disabled post-cutover.
- Observations and event logs are append-only (defense-in-depth).

## What “Frozen” Means
### 1) V1 schema evolution is blocked
- No new fields/columns may be added to V1 contract entities.
- No field type changes, renames, or semantic repurposing.

### 2) V1 write paths are eventually disabled
- When a V2 side-by-side schema is introduced, **V1 becomes read-only**.
- This repo already contains DB enforcement to reject writes to any table named `*_v1`.

### 3) Only bug-fix migrations are allowed
Bug fixes that must touch V1 require:
- Explicit approval (see workflow below)
- A V1 contract version bump
- A changelog entry

## Canonical References (Deliverables)
- V1 contract version: `contracts/v1_contract_version.txt`
- Immutable field registry: `contracts/immutable_field_registry_v1.json`
- V1 contract changelog: `contracts/v1_contract_changelog.md`

These are the canonical sources for V1 compatibility.

## DB Enforcement (Writes Rejected on `*_v1`)
Migration: `services/api/migrations/028_freeze_v1_contracts.sql`

Behavior:
- Any `INSERT`, `UPDATE`, or `DELETE` against a `*_v1` table is rejected.
- Controlled escape hatch for maintenance:

```sql
BEGIN;
SET LOCAL savo.allow_v1_writes = 'on';
-- exceptional maintenance DML
COMMIT;
```

## Approval Workflow (Required)
Any change that affects the V1 registry requires:
1. Bump `contracts/v1_contract_version.txt`
2. Add an entry to `contracts/v1_contract_changelog.md` including:
   - Summary of change
   - Risk assessment
   - `Approved-by: <name>`
3. Regenerate and commit `contracts/immutable_field_registry_v1.json`

## CI/Review Guardrails
The repo includes a CI guard script that fails when:
- The V1 registry changes without a version bump and changelog entry
- A migration attempts to alter a V1 contract entity without following the workflow

Run locally:
```bash
python scripts/check_v1_contracts_immutable.py
```
