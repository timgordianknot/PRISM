# Skill: Data Stewardship

Use this skill when work changes persisted data, CSV import/export behavior, validation, quarantine, or schema expectations.

## Goals

- Protect user data from accidental loss or silent corruption.
- Preserve invalid imported rows in quarantine with clear reasons.
- Keep data shape expectations documented and tested.
- Make migrations or manual cleanup explicit before deployment.

## Current data model

PRISM stores four top-level collections:

- `transactions`
- `contacts`
- `deals`
- `tasks`

Runtime local files:

- `data/fincrm_data.json`
- `data/fincrm_quarantine.json`

## Checklist

Before data-related changes:

- [ ] Read `docs/ai/project-context.md`.
- [ ] Inspect validation logic in `apps/fincrm_dashboard.py`.
- [ ] Inspect API persistence logic in `api/main.py` if backend sync is affected.
- [ ] Identify whether existing JSON files need migration, backup, or manual cleanup.

During implementation:

- [ ] Keep top-level data sections explicit.
- [ ] Validate imported CSV rows before accepting them.
- [ ] Send invalid rows to quarantine with enough reasons to fix them later.
- [ ] Avoid silent drops, broad exception swallowing, or lossy coercion.
- [ ] Use atomic write patterns for persisted JSON where possible.
- [ ] Keep API and UI assumptions aligned.

Before finishing:

- [ ] Add or update tests for schema, validation, quarantine, or persistence behavior.
- [ ] Run `make test`.
- [ ] Update `docs/ai/project-context.md` if stable data behavior changed.
- [ ] Add a handoff note if there are migration risks, manual cleanup steps, or open data questions.

## Red flags

- Changing field names without migration notes.
- Treating runtime `data/` files as generic source files.
- Allowing malformed CSV rows to disappear.
- Letting UI and API normalize data differently without documenting the difference.
- Using production-like data in tests or docs.

## Memory responsibilities

- Stable data model changes belong in `docs/ai/project-context.md`.
- One-off debugging or cleanup findings belong in `docs/ai/handoffs/` or an investigation note.
- Migration, backup, and restore procedures belong in `docs/ai/runbooks/`.
