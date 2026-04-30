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
