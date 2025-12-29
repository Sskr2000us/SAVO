# SAVO Specs (source of truth)

This folder contains the **source-controlled JSON specs** used to implement SAVO MVP.

## Files
- `prompt-pack.gpt-5.2.json` — Prompt pack, tasks, and output schemas
- `engineering-plan.mvp.json` — Epics/stories/tasks/estimates and sprint recommendations
- `ui-spec.ant.figma-ready.json` — Figma-ready UI spec (tokens/components/screens)

## How to use
1. Treat `engineering-plan.mvp.json` as the work backlog.
2. Treat `prompt-pack.gpt-5.2.json` as the AI contract.
3. Treat `ui-spec.ant.figma-ready.json` as the UI contract.

When implementing, keep the runtime API responses aligned with the schemas in the prompt pack.
