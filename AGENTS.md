# Agent Instructions

This repository uses Markdown memory files so AI agents can preserve useful context across sessions without relying on chat history.

## Start-of-work checklist

Before substantial work, read:

1. `docs/ai/project-context.md` for the stable project overview.
2. `docs/ai/README.md` for the memory system rules.
3. `docs/ai/current-state.md` for current priorities and known gaps.
4. `docs/ai/agent-roles.md` and `docs/ai/workflows.md` when choosing a role or workflow.
5. Relevant skill checklists in `docs/ai/skills/` for security, GitHub preservation, data, deployment, or instruction-sync work.
6. Relevant recent handoffs in `docs/ai/handoffs/` if continuing prior work.

For tiny edits, still skim the relevant code and update memory only when something durable is learned.

## Development commands

- Install dependencies: `make install`
- Run tests: `make test`
- Run Streamlit UI: `make run-ui`
- Run FastAPI backend: `make run-api`

## Memory update rules

Update AI memory when work changes or discovers durable project knowledge:

- architecture, data model, or integration behavior
- deployment, infrastructure, CI/CD, or environment setup
- agent/subagent workflow
- recurring bugs, debugging discoveries, or operational risks
- security, permissions, or data durability assumptions

Do not create memory files for routine typo fixes, small copy edits, or obvious local changes.

## Skill checklists

Use the smallest relevant skill checklist when a task touches a specialized concern:

- `docs/ai/skills/security-and-secrets.md`: tokens, auth, secrets, permissions, or sensitive data.
- `docs/ai/skills/github-preservation.md`: commits, branches, PRs, backups, curriculum, or durable docs.
- `docs/ai/skills/data-stewardship.md`: JSON storage, CSV import/export, validation, schema, or quarantine behavior.
- `docs/ai/skills/deployment-readiness.md`: hosting, environments, CI/CD deploys, rollback, or Terraform readiness.
- `docs/ai/skills/instruction-sync.md`: Cursor, Codex, ChatGPT, AGENTS files, rules, or cross-tool instruction drift.

## Handoffs

Before finishing substantial work, create or update a concise handoff in `docs/ai/handoffs/`.
Use `docs/ai/templates/handoff-template.md` and include:

- task summary
- files changed
- important implementation details
- commands/tests run
- known risks or gaps
- suggested follow-ups

## Decisions

For meaningful technical choices, add a decision record in `docs/ai/decisions/` using `docs/ai/templates/decision-record-template.md`.
Keep each record short, factual, and linked to code or PRs when available.

## Documentation style

- Prefer concise Markdown with clear headings.
- Keep durable context in stable files, not only in chat.
- Link to code paths, issues, PRs, and deployment artifacts when useful.
- Avoid secrets or credentials in memory files.
