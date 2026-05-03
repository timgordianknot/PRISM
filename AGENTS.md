# Agent Instructions

This repository uses Markdown memory files so AI agents can preserve useful context across sessions without relying on chat history.

## Start-of-work checklist

Before substantial work, read:

1. `docs/ai/project-context.md` for the stable project overview.
2. `docs/ai/README.md` for the memory system rules.
3. `docs/ai/current-state.md` for current priorities and known gaps.
4. `docs/ai/agent-roles.md` and `docs/ai/workflows.md` when choosing a role or workflow.
5. Relevant recent handoffs in `docs/ai/handoffs/` if continuing prior work.

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

## Cursor Cloud specific instructions

This is a Python-only project (no Node.js/npm). All dependencies are managed via `pip install -r requirements.txt`.

### Services

| Service | Command | Port | Notes |
|---------|---------|------|-------|
| FastAPI backend | `uvicorn api.main:app --reload` | 8000 | Optional; dashboard works without it via local JSON files |
| Streamlit dashboard | `streamlit run apps/fincrm_dashboard.py --server.headless true --server.port 8501` | 8501 | Primary UI |

### Running tests

```bash
python3 -m pytest -q
```

All 11 tests run in-process (no external services needed). Tests use FastAPI's TestClient via httpx.

### Key notes

- No external databases or Docker required — persistence is flat JSON files in `data/`.
- Auth tokens (`PRISM_READ_TOKEN`, `PRISM_ADMIN_TOKEN`) are optional; without them the API runs in open-access mode.
- The Streamlit dashboard has a sidebar toggle "Use FastAPI backend" to switch between local-file mode and API-backed mode.
- Standard commands are documented in `README.md` and the `Makefile` (`make install`, `make test`, `make run-api`, `make run-ui`).

## Multi-agent cooperation (Cursor Cloud + Codex)

Multiple AI agents (Cursor Cloud, Codex, etc.) may operate on this repo concurrently. Follow these rules to avoid conflicts:

### Branch discipline

- Always work on your own feature branch (`macro/<name>-<id>` for Cursor, or your own prefix for Codex).
- Never force-push or rebase another agent's branch.
- Before starting work, run `git fetch origin` and check for recent branches/PRs from the other agent to avoid duplicate effort.

### File-level coordination

- Do not edit files that another agent's open PR already modifies, unless explicitly asked to resolve a conflict.
- `data/` directory is gitignored runtime state — never commit it. Both agents can read/write it at runtime without conflict.
- `AGENTS.md` is shared documentation — append-only edits are safe; avoid rewriting existing sections written by the other agent.

### Shared runtime state

- FastAPI default port: **8000**. Streamlit default port: **8501**. If both agents need to run services simultaneously, use `--port` flags with different ports (e.g. 8002, 8502).
- The JSON data files in `data/` are single-writer — do not run two FastAPI instances pointed at the same data files concurrently.

### Communication protocol

- If you need to leave a note for the other agent, add it as a comment in the relevant PR or append a clearly-labeled section in `AGENTS.md`.
- Prefix PR titles with your agent name (e.g. `[Cursor]` or `[Codex]`) so ownership is clear.
- When both agents are asked to work on the same feature, one should implement and the other should review — not both implement independently.
