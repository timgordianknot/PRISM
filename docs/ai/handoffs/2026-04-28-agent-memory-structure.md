# Agent Handoff: Agent Memory Structure

## Task summary

- What was requested: Implement a lightweight Markdown memory structure for Cursor/Codex agents and subagents, then add simple agent role, workflow, current-state, and skill checklist docs.
- Final outcome: Added repo-level agent instructions, AI memory docs, coordination docs, focused skill checklists, templates, a local development runbook, and an initial decision record.

## Files changed

- `AGENTS.md`: Defines start-of-work checklist, development commands, and memory update rules for agents.
- `docs/ai/README.md`: Explains the memory system and directory map.
- `docs/ai/project-context.md`: Seeds stable PRISM product, architecture, commands, data, CI, and deployment context.
- `docs/ai/agent-roles.md`: Defines reusable Planner, Builder, QA, Librarian, Release Manager, Architecture Reviewer, and DevOps roles.
- `docs/ai/workflows.md`: Documents simple workflows for features, bugs, docs cleanup, releases, and environment/CI work.
- `docs/ai/current-state.md`: Captures a short snapshot of current priorities, known gaps, and next useful improvements.
- `docs/ai/skills/`: Adds focused checklists for security/secrets, GitHub preservation, data stewardship, deployment readiness, and instruction sync.
- `docs/ai/templates/`: Adds reusable templates for handoffs, decisions, investigations, runbooks, and release notes.
- `docs/ai/runbooks/local-development.md`: Documents setup, test, UI, and API procedures.
- `docs/ai/decisions/0001-use-markdown-agent-memory.md`: Records the decision to use lightweight Markdown memory.
- `docs/ai/handoffs/2026-04-28-agent-memory-structure.md`: Captures this handoff.

## Important implementation details

- The structure is intentionally small and Markdown-only.
- Agents should update memory only when durable knowledge changes, not for routine edits.
- The current project context was seeded from `README.md`, `Makefile`, `.github/workflows/ci.yml`, `api/main.py`, and `apps/fincrm_dashboard.py`.
- The recommended operating loop is now documented as `Planner -> Builder -> QA -> Librarian`, with optional Release Manager, Architecture Reviewer, and DevOps roles for specialized work.
- Skill checklists are designed as lightweight safeguards, not new required agents.

## Commands and tests run

- `make test`: failed initially because `pytest` was not installed in the cloud environment.
- `make install && make test`: installed declared dependencies and passed, `11 passed in 0.52s`.
- `make test`: passed after adding coordination docs, `11 passed in 0.43s`.
- `make test`: passed after adding skills docs, `11 passed in 0.45s`.

## Known risks or gaps

- The context reflects the repository state on 2026-04-28 and should be refreshed when architecture, deployment, or CI changes.
- No production deployment runbook exists yet because the repo currently documents local UI/API commands and CI only.

## Suggested follow-ups

- Add deployment and rollback runbooks when dev/prod infrastructure is finalized.
- Add more decision records when CI/CD, Terraform, branch strategy, or agent subagent rules become concrete.

## Links

- PR: Registered for approval
- Issue/task: N/A
- Deployment or run: N/A
