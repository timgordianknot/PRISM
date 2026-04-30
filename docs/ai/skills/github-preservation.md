# Skill: GitHub Preservation

Use this skill when work creates code, documentation, curriculum, prompts, workflow notes, or other artifacts that should survive beyond the current chat.

## Purpose

Keep important work backed up, reviewable, and recoverable through GitHub and Markdown memory.

## When to use this skill

- Making meaningful code or documentation changes.
- Capturing curriculum, learning materials, prompts, or agent instructions.
- Finishing a multi-step agent session.
- Preparing work for review or handoff.
- Moving knowledge out of chat into durable files.

## Checklist

- Check the current branch and worktree before editing.
- Preserve user changes; do not revert unrelated work.
- Keep changes grouped by logical purpose.
- Update Markdown memory when durable context changed.
- Run relevant checks before finalizing when possible.
- Commit with a clear message.
- Push the branch to GitHub.
- Create or update the PR registration when required by the workflow.

## What belongs in GitHub

- Source code.
- Tests.
- Project docs.
- Runbooks.
- Decision records.
- Agent handoffs.
- Reusable prompts or curriculum files that are not private.

## What should not be committed

- Secrets, tokens, or private keys.
- Local-only runtime data unless intentionally required.
- Generated cache files.
- Personal notes that do not belong to the repo.
- Temporary debug output.

## Memory responsibilities

- Add or update `docs/ai/handoffs/` for substantial work.
- Update `docs/ai/current-state.md` when priorities, known gaps, or active operating assumptions change.
- Add a decision record for meaningful Git, branch, release, or preservation policy choices.

## Handoff questions

- What changed?
- What was backed up to GitHub?
- What checks passed or failed?
- What still exists only outside the repo?
- What should the next agent review first?
