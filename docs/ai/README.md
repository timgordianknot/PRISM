# AI Memory System

This directory preserves durable project context for humans, Cursor agents, Codex agents, and subagents.
Use it to reduce repeated discovery work and make handoffs reliable across sessions.

## Directory map

- `project-context.md`: stable overview of the product, architecture, commands, data storage, and deployment assumptions.
- `decisions/`: short decision records for meaningful technical choices.
- `handoffs/`: agent-to-agent notes after substantial work.
- `runbooks/`: operational procedures for setup, deploys, rollbacks, migrations, and incident response.
- `templates/`: reusable Markdown templates for consistent memory notes.

## When to update memory

Update these files when work creates or discovers knowledge that should survive the current chat:

- architecture, data model, or integration changes
- deployment, infrastructure, CI/CD, or environment changes
- new agent or subagent workflow expectations
- recurring bugs or debugging discoveries
- security, permission, data durability, or operational assumptions
- important product decisions

Do not add new memory notes for every minor edit. If a change is obvious from the diff and has no lasting context, the commit and PR are enough.

## How agents should use this system

1. Read `AGENTS.md` and `docs/ai/project-context.md` before substantial work.
2. Check recent handoffs in `docs/ai/handoffs/` when continuing an existing thread of work.
3. Update the smallest relevant memory file when durable context changes.
4. Add a decision record for meaningful architecture, deployment, product, or workflow choices.
5. Add a handoff before finishing substantial work.

## Naming conventions

- Decision records: `NNNN-short-kebab-title.md`, for example `0001-use-github-actions-for-ci.md`.
- Handoffs: `YYYY-MM-DD-short-kebab-title.md`.
- Runbooks: short kebab-case names, for example `local-development.md` or `production-rollback.md`.

Keep entries concise, factual, and link to code paths, issues, PRs, or deployment artifacts when useful.
