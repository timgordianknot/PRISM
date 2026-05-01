# AGENTS.md

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
