# Agent Roles

Use these roles to keep AI work focused. A single agent can play more than one role, but name the active role in handoffs when it affects the work.

## Default loop

```text
Planner -> Builder -> QA -> Librarian
```

- Planner clarifies scope and risks.
- Builder changes code or docs.
- QA verifies behavior and checks for gaps.
- Librarian preserves durable memory.

## Planner Agent

**Purpose:** Turn a request into a small, actionable plan.

**Use when:**

- the task has unclear scope
- multiple implementation paths are possible
- architecture, deployment, or data flow may change

**Inputs:**

- user request
- `docs/ai/project-context.md`
- relevant recent handoffs

**Outputs:**

- concise plan or implementation checklist
- open questions only when needed
- risks or dependencies worth checking before edits

**Memory responsibilities:**

- create a decision record if the plan chooses a meaningful architecture, workflow, or deployment direction
- avoid writing handoffs unless the planning work itself leaves durable context

## Builder Agent

**Purpose:** Implement the requested code or documentation change.

**Use when:**

- scope is clear enough to edit files
- a plan has been accepted
- an issue needs a concrete fix

**Inputs:**

- current branch and git status
- relevant code paths
- accepted plan or user request
- `AGENTS.md`

**Outputs:**

- focused code/docs changes
- passing relevant checks where possible
- commit-ready diff

**Memory responsibilities:**

- update `docs/ai/project-context.md` when stable project behavior changes
- add or update runbooks when operational steps change
- add a handoff for substantial work

## QA Agent

**Purpose:** Verify changes and look for breakage, missing tests, and risky assumptions.

**Use when:**

- a branch is ready for validation
- tests fail or coverage is uncertain
- behavior crosses UI, API, data, or CI boundaries

**Inputs:**

- changed files
- existing tests
- relevant runbooks
- expected behavior from the user or docs

**Outputs:**

- commands/tests run and results
- issues found, ordered by severity
- test gaps or residual risks

**Memory responsibilities:**

- record recurring failures or debugging discoveries in a handoff or investigation note
- update runbooks if verification steps changed

## Librarian Agent

**Purpose:** Keep the AI memory system accurate, concise, and easy to use.

**Use when:**

- several agents have worked on the repo
- docs feel stale or scattered
- a release, deployment, or architecture change needs memory cleanup

**Inputs:**

- `docs/ai/`
- recent handoffs
- recent commits or PRs
- current repo layout

**Outputs:**

- cleaned or consolidated memory docs
- stale notes identified or corrected
- updated current state

**Memory responsibilities:**

- keep `docs/ai/current-state.md` short and current
- prune duplication where possible
- preserve useful links and remove vague notes

## Release Manager Agent

**Purpose:** Prepare a branch or set of changes for merge, deployment, or public release.

**Use when:**

- moving work from development toward production
- preparing release notes
- checking readiness before merge

**Inputs:**

- git diff or commit range
- test/CI status
- deployment runbooks
- release notes template

**Outputs:**

- release summary
- validation checklist
- risks and rollback notes

**Memory responsibilities:**

- update release notes or handoff notes
- add deployment/rollback runbooks once environments exist

## Architecture Reviewer Agent

**Purpose:** Keep the system simple and coherent as it grows.

**Use when:**

- changes introduce new modules, services, persistence, or infrastructure
- code starts duplicating behavior
- an implementation feels more complex than the problem

**Inputs:**

- affected code paths
- `docs/ai/project-context.md`
- decision records

**Outputs:**

- risks, simplification opportunities, and missing decisions
- recommendations grounded in existing patterns

**Memory responsibilities:**

- add decision records for accepted architecture choices
- update project context when architecture changes

## Environment and DevOps Agent

**Purpose:** Maintain local setup, CI/CD, deployment, and infrastructure documentation.

**Use when:**

- dependencies, CI, cloud environments, secrets, or deployment flow changes
- Terraform or hosting is introduced
- dev/prod environment behavior needs documentation

**Inputs:**

- `Makefile`
- `.github/workflows/`
- deployment files
- runbooks
- environment setup notes

**Outputs:**

- updated CI or setup docs
- runbook changes
- risk notes for secrets, deploys, and rollback

**Memory responsibilities:**

- keep runbooks current
- update `docs/ai/project-context.md` for CI/CD or deployment changes
- add decision records for branch strategy, deployment model, or infrastructure choices
