# Skill: Instruction Sync

## Purpose

Keep ChatGPT, Codex, Cursor, repo Markdown, and other AI tool instructions aligned so agents do not follow conflicting guidance.

## Use this skill when

- adding or changing `AGENTS.md`, Cursor rules, Codex instructions, or ChatGPT prompts
- copying instructions between tools or repositories
- an agent reports conflicting rules
- a workflow changes and multiple docs need to agree
- onboarding a new tool, laptop, cloud agent, or repository

## Checklist

1. Identify the instruction sources involved:
   - `AGENTS.md`
   - `docs/ai/`
   - Cursor rules or project settings
   - Codex or ChatGPT custom instructions
   - external notebooks, curriculum docs, or network notes
2. Confirm the durable repo source of truth before changing external prompts.
3. Keep shared principles consistent:
   - read project docs before substantial work
   - preserve important work in GitHub
   - update Markdown memory when durable context changes
   - avoid secrets in docs and commits
   - prefer simple, maintainable systems
4. Remove outdated or duplicated instructions where possible.
5. If external tool instructions cannot be edited from this repo, document what should be copied out.
6. Record meaningful instruction changes in a handoff or decision record.

## Warning signs

- different tools disagree about branch strategy, testing, or memory rules
- useful context exists only in chat history
- agents repeatedly rediscover the same setup steps
- a prompt says to preserve docs but the repo has no matching instructions
- local, cloud, and GitHub workflows have drifted apart

## Outputs

- synchronized repo instruction docs
- concise copy-ready text for external tool instructions when needed
- updated `docs/ai/current-state.md` if priorities or known gaps change
- handoff note describing what changed and what still needs syncing

## Related files

- `AGENTS.md`
- `docs/ai/README.md`
- `docs/ai/project-context.md`
- `docs/ai/current-state.md`
- `docs/ai/workflows.md`
- `docs/ai/skills/github-preservation.md`
- `docs/ai/skills/security-and-secrets.md`
