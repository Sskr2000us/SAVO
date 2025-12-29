# SAVO — Smart home cooking, powered by SmartChef

SAVO is a smart home cooking product powered by **SmartChef**: a system that helps users plan, prep, and cook reliably using connected appliances and guided workflows.

This repository is the product + engineering home for SAVO.

## What’s here
- `docs/` — Product requirements, architecture, and decisions
- `apps/` — User-facing applications (to be selected/scaffolded)
- `services/` — Backend services (to be selected/scaffolded)
- `device/` — Device/IoT protocol notes, simulators, firmware (as applicable)

## Key docs
- `docs/PRD.md` — Product requirements
- `docs/Software_Architecture.md` — Production-ready architecture (MVP → scale)
- `docs/Build_Plan.md` — Sprint-by-sprint build plan mapped to JSON specs
- `docs/spec/` — Source-controlled JSON specs (prompts, engineering plan, UI spec)
- `docs/decisions/` — ADRs (decisions and rationale)

## Next decisions (to scaffold code)
- Target UX surface: mobile app, web app, or both
- Device strategy: integrate existing smart ovens/thermometers vs dedicated hardware
- Cloud strategy: local-only vs cloud-assisted

See `docs/PRD.md` to start.
