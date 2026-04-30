# Current State

Last updated: 2026-04-28

Use this file as a quick orientation snapshot. Keep it short and update it when priorities, gaps, or active work change.

## App status

PRISM currently has:

- Streamlit dashboard in `apps/fincrm_dashboard.py`.
- Optional FastAPI backend in `api/main.py`.
- Local JSON storage under `data/` at runtime.
- CSV import/export and validation.
- Quarantine flow for invalid rows.
- Pytest suite covering API behavior, dashboard CSV handling, and local data behavior.
- GitHub Actions workflow that runs tests on pushes and pull requests.

## Current operating focus

- Keep the AI memory system lightweight and useful.
- Preserve durable context for agents and subagents in Markdown.
- Avoid adding process that is heavier than the current prototype needs.
- Add deployment, release, and infrastructure docs when those flows become concrete.
- Use focused skills in `docs/ai/skills/` for security, preservation, data, deployment, and instruction-sync checks.

## Recommended agent loop

```text
Planner -> Builder -> QA -> Librarian
```

- Planner scopes the smallest safe path.
- Builder makes the code or documentation change.
- QA validates behavior and identifies gaps.
- Librarian preserves durable memory and removes stale notes.

For operational changes, include the DevOps Agent. For releases, include the Release Manager Agent.

## Known gaps

- No documented production deployment environment yet.
- No deployment or rollback runbook yet.
- No Terraform configuration yet.
- No formal dev/prod branch promotion workflow yet.
- No documented secrets management process for deployed environments yet.
- No formal cross-tool instruction sync cadence yet.

## Next good improvements

- Add deployment and rollback runbooks after hosting is chosen.
- Add a decision record for branch strategy once dev/prod flow is finalized.
- Add CI/CD expansion notes if linting, formatting, type checks, security scans, or deploy jobs are introduced.
- Use the security, GitHub preservation, data stewardship, deployment readiness, and instruction sync skills as lightweight checklists during relevant work.
- Keep handoffs current after substantial agent work.

