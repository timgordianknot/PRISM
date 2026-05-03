# Decision Record: Keep PRISM on main while extracting the shared template

- **Status:** accepted
- **Date:** 2026-04-28
- **Owner:** Codex agent
- **Related work:** `v3.0.0`, `.cursor/environment.json`, `AGENTS.md`, `docs/ai/`

## Context

`PRISM` already ships releases from `main`, including the `v3.0.0` baseline. New workflow work was added in narrow branches for agent memory and Cursor Cloud bootstrap. A broader migration to long-lived `dev` and `prod` branches would add risk while the repo is still absorbing those workflow additions.

## Decision

Keep `PRISM` on its current `main`-based release flow for now. Merge the narrow workflow branches into the released baseline, validate them, and extract the reusable workflow system into a separate shared template repo. Reserve `dev`/`prod` branching as the default for future adopters of the new template.

## Consequences

- `PRISM` keeps its current release history and avoids branch-model churn during workflow integration.
- Shared workflow assets can still be generalized from a working production-like seed.
- Future repos can adopt `dev`/`prod` without forcing an immediate migration inside `PRISM`.
- If `PRISM` later needs environment promotion branches, that migration will remain a separate change.

## Alternatives considered

- Immediate `dev`/`prod` migration inside `PRISM`: rejected because it adds risk without improving the current workflow integration scope.
- Extract the template first without merging the workflow branches: rejected because the merged `PRISM` state is the most reliable seed for the shared template.
