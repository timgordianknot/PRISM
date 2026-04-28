# Runbook: Local Development

## Purpose

Start and validate the PRISM FinCRM application on a local development machine or cloud agent.

## Preconditions

- Python 3.12 is preferred because CI uses Python 3.12.
- Repository dependencies are listed in `requirements.txt`.
- Optional API permissions use `PRISM_READ_TOKEN` and `PRISM_ADMIN_TOKEN`.
- Cursor Cloud startup uses `.cursor/environment.json` to run `make install` automatically for remote agents.

## Steps

1. Install dependencies:

   ```bash
   make install
   ```

   If `make` is unavailable locally, use:

   ```bash
   python -m pip install -r requirements.txt
   ```

2. Run the automated tests:

   ```bash
   make test
   ```

3. Start the optional FastAPI backend:

   ```bash
   make run-api
   ```

4. In a separate terminal, start the Streamlit UI:

   ```bash
   make run-ui
   ```

5. Open the Streamlit URL shown in the terminal and enable `Use FastAPI backend` in the sidebar if testing backend sync.

## Verification

- `make test` passes.
- `GET /health` returns `{"status": "ok"}` when the API is running.
- The Streamlit dashboard loads without import or data-file errors.
- CSV import keeps invalid rows in quarantine instead of dropping them.

## Rollback or Recovery

- If local JSON data becomes invalid, stop the app and inspect files under `data/`.
- The backend and UI normalize malformed persisted data where possible, but manual cleanup may still be needed for bad local edits.
- Do not commit local data files unless they are intentionally part of a task.

## Known Risks

- If `PRISM_READ_TOKEN` or `PRISM_ADMIN_TOKEN` are set, sidebar API requests need a matching token.
- Without configured tokens, the API allows open local access for prototyping.
- Streamlit and FastAPI are separate processes; backend sync testing needs both running.

## Related References

- `README.md`
- `Makefile`
- `.cursor/environment.json`
- `api/main.py`
- `apps/fincrm_dashboard.py`
