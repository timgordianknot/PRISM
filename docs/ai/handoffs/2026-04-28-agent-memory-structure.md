# Agent Handoff: Agent Memory Structure

## Task summary

- What was requested: Implement a lightweight Markdown memory structure for Cursor/Codex agents and subagents.
- Final outcome: Added repo-level agent instructions, AI memory docs, templates, a local development runbook, and an initial decision record.

## Files changed

- `AGENTS.md`: Defines start-of-work checklist, development commands, and memory update rules for agents.
- `docs/ai/README.md`: Explains the memory system and directory map.
- `docs/ai/project-context.md`: Seeds stable PRISM product, architecture, commands, data, CI, and deployment context.
- `docs/ai/templates/`: Adds reusable templates for handoffs, decisions, investigations, runbooks, and release notes.
- `docs/ai/runbooks/local-development.md`: Documents setup, test, UI, and API procedures.
- `docs/ai/decisions/0001-use-markdown-agent-memory.md`: Records the decision to use lightweight Markdown memory.
- `docs/ai/handoffs/2026-04-28-agent-memory-structure.md`: Captures this handoff.

## Important implementation details

- The structure is intentionally small and Markdown-only.
- Agents should update memory only when durable knowledge changes, not for routine edits.
- The current project context was seeded from `README.md`, `Makefile`, `.github/workflows/ci.yml`, `api/main.py`, and `apps/fincrm_dashboard.py`.

## Commands and tests run

- Pending final verification.

## Known risks or gaps

- The context reflects the repository state on 2026-04-28 and should be refreshed when architecture, deployment, or CI changes.
- No production deployment runbook exists yet because the repo currently documents local UI/API commands and CI only.

## Suggested follow-ups

- Add deployment and rollback runbooks when dev/prod infrastructure is finalized.
- Add more decision records when CI/CD, Terraform, branch strategy, or agent subagent rules become concrete.

## Links

- PR: Pending
- Issue/task: N/A
- Deployment or run: N/A
