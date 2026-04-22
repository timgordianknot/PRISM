# PRISM v3.0.0 (Proposed)

This release focuses on reliability, data safety, and operational readiness.

## Highlights

- **Stabilized dashboard overview metrics**
  - Removed fragile expression patterns that could trigger runtime failures.
- **Robust CSV import/export**
  - Switched to Python `csv` reader/writer behavior for proper quoted-field handling.
- **Data corruption resilience**
  - Local dashboard and API paths now recover safely from malformed JSON.
  - Corrupt local dashboard data is backed up to `*.corrupt.json` before self-heal.
- **Atomic persistence writes**
  - JSON writes now use atomic replace semantics to reduce risk of partial/truncated files.
- **Quarantine API correctness**
  - `/quarantine/items` now reports the count of records actually appended.
  - Quarantine payload handling is tolerant and filters non-dict entries.
- **Expanded verification**
  - Added regression and integration-style tests for restore/delete and malformed flows.
  - Added CI workflow to run tests on push/PR.
- **Developer workflow improvements**
  - Added `Makefile` targets for install/test/run-api/run-ui.
  - Added ignore rules for Python cache artifacts.
  - Updated Streamlit width API usage to remove deprecation warnings.

## Validation Summary

- Automated tests: `11 passed`
- Smoke checks:
  - API health endpoint (`GET /health`) responded OK
  - Streamlit UI endpoint responded HTTP 200

## Quick Start (v3)

```bash
make install
make test
make run-api
make run-ui
```

## Risk / Compatibility Notes

- No schema migration is required for existing JSON data files.
- API token behavior remains unchanged:
  - If tokens are not configured, API defaults to open admin mode for local prototyping.
  - Set `PRISM_READ_TOKEN` / `PRISM_ADMIN_TOKEN` for controlled access.

