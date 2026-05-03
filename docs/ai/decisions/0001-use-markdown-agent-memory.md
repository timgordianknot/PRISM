# Decision Record: Use Markdown agent memory

- **Status:** accepted
- **Date:** 2026-04-28
- **Owner:** Cursor agent
- **Related work:** `AGENTS.md`, `docs/ai/`

## Context

The project already had code, tests, and CI, but agent and subagent work was not consistently preserving durable context outside chat sessions. Future agents need a simple way to understand project structure, decisions, handoffs, and operational notes without relying on prior conversations.

## Decision

Use a lightweight Markdown memory system in `docs/ai/` plus top-level `AGENTS.md` instructions. The system includes project context, decision records, handoffs, runbooks, and reusable templates.

## Consequences

- Agents have a predictable place to read and write durable context.
- Human maintainers can review memory updates in normal Git diffs.
- The process stays lightweight because memory updates are required only for durable discoveries or meaningful changes.
- Documentation can drift if agents do not update it when project behavior changes.

## Alternatives considered

- Chat-only memory: rejected because it is not durable across tools, sessions, or repositories.
- A heavier documentation portal: rejected because the current repo needs low-friction Markdown more than a new docs platform.

