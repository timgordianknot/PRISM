# Skill: Deployment Readiness

Use this skill when preparing PRISM for dev, staging, production, or any hosted environment.

## Purpose

Make deployment practical and reversible without overbuilding infrastructure before the app needs it.

## Use this skill when

- hosting provider or cloud infrastructure is being selected
- deployment scripts, CI jobs, or Terraform are introduced
- dev/prod branch or environment promotion is discussed
- environment variables, secrets, data paths, or storage behavior change
- rollback, monitoring, or health checks need documentation

## Checklist

Before deployment, confirm:

- [ ] hosting target is named
- [ ] dev and prod environment differences are documented
- [ ] required environment variables are listed
- [ ] secrets are configured outside Git
- [ ] runtime data storage is separated by environment
- [ ] `GET /health` or equivalent health check is available
- [ ] deployment trigger is documented
- [ ] rollback or recovery path is documented
- [ ] logs or monitoring access is known
- [ ] tests pass before deploy

## Branch and environment notes

Do not assume a permanent `dev` and `prod` branch model is required. For this repo, decide branch strategy based on the hosting setup and release needs.

Common options:

- feature branch -> pull request -> `main` -> production deploy
- feature branch -> pull request -> `dev` -> dev deploy -> release PR -> `main` or `prod`
- pull request preview deploys plus `main` production deploy

Record the accepted model in `docs/ai/decisions/`.

## Memory responsibilities

Update:

- `docs/ai/current-state.md` when deployment status or gaps change
- `docs/ai/project-context.md` when deployment architecture becomes stable
- `docs/ai/runbooks/` for deploy, rollback, recovery, and environment setup procedures
- `docs/ai/decisions/` for branch strategy, hosting provider, Terraform adoption, or production data choices

## Stop and ask

Ask for human confirmation before:

- choosing a paid hosting provider
- changing DNS, public URLs, or production secrets
- adding Terraform-managed resources
- changing production data paths or persistence behavior

