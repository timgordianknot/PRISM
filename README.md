# PRISM

## Run Streamlit Dashboard

```powershell
pip install -r requirements.txt
streamlit run apps/fincrm_dashboard.py
```

## Optional FastAPI Backend

Run this in a second terminal from the same folder:

```powershell
uvicorn api.main:app --reload
```

Then in the Streamlit sidebar, enable `Use FastAPI backend`.

### API Permissions (recommended for durability across devices)

FastAPI can enforce permissions via environment variables on the backend machine:
- `PRISM_READ_TOKEN`: allows `GET /data` and `GET /quarantine`
- `PRISM_ADMIN_TOKEN`: allows `PUT /data`, `POST /quarantine/items`, `DELETE /quarantine/{item_id}`, and restore operations

In the Streamlit sidebar, set the `API token` to the appropriate token (admin for restore/delete).

## Validation + Quarantine

When importing CSV (and when saving edited tasks), invalid rows are not dropped.
They are stored in the quarantine bin and can be reviewed/restored from the `Quarantine` page.

When backend sync is enabled, quarantines are also appended to the backend so you can restore them on another machine.

## Data Location

- Local file storage: `data/fincrm_data.json`
- Quarantine (durability): `data/fincrm_quarantine.json`
- API endpoints:
  - `GET /health`
  - `GET /data`
  - `PUT /data`
  - `GET /quarantine`
  - `POST /quarantine/items`
  - `DELETE /quarantine/{item_id}`
  - `POST /quarantine/{item_id}/restore`
