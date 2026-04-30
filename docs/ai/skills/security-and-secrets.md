# Skill: Security and Secrets

Use this skill whenever work touches authentication, authorization, tokens, environment variables, deployment, data access, or external services.

## Purpose

Protect credentials, permissions, user data, and runtime configuration while keeping the app simple to operate.

## When to use

- Adding or changing API authentication or authorization.
- Reading, writing, or documenting environment variables.
- Preparing deployment, CI/CD, Terraform, or hosting changes.
- Handling data files, backups, logs, exports, or uploaded content.
- Reviewing a PR that changes security-sensitive behavior.

## Checklist

- Do not commit secrets, tokens, private keys, `.env` files, credentials, or personal data.
- Document required environment variables by name only, not by value.
- Confirm `.gitignore` covers local secret and runtime-data files when relevant.
- Prefer least-privilege permissions for tokens, CI jobs, deploy keys, and cloud roles.
- Avoid logging secrets, API tokens, request headers, or sensitive payloads.
- Treat local runtime files under `data/` as environment-specific unless a task explicitly says otherwise.
- For PRISM API permissions, preserve the intended split:
  - `PRISM_READ_TOKEN` for read access.
  - `PRISM_ADMIN_TOKEN` for write, delete, and restore access.
- If security behavior changes, add or update tests where practical.

## Memory responsibilities

- Update `docs/ai/project-context.md` if stable security behavior changes.
- Add or update a runbook if setup, deploy, rollback, or secret rotation steps change.
- Add a decision record for meaningful auth, permission, or secrets-management choices.
- Record unresolved risks in the handoff.

## Red flags

- A diff contains a real-looking token, key, password, private URL, or credential.
- A deployment step requires manual secret setup but no runbook explains it.
- Runtime data is about to be committed accidentally.
- API auth becomes broader than documented.
