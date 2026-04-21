"""PRISM FinCRM dashboard.

Coherent implementation order:
1) Local JSON persistence.
2) CSV import/export utilities.
3) Optional FastAPI backend sync (fallback-safe).
"""

from __future__ import annotations

import uuid
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

import streamlit as st

try:
    import requests
except ImportError:
    requests = None

from prism_schema import (
    ALLOWED_CATEGORIES,
    ALLOWED_CONTACT_STATUSES,
    ALLOWED_DEAL_STAGES,
    ALLOWED_TASK_PRIORITIES,
    normalize_data as _normalize_data,
    parse_bool as _parse_bool,
    parse_iso_date_value as _parse_iso_date_value,
    safe_float as _safe_float,
    validate_row,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = PROJECT_ROOT / "data" / "fincrm_data.json"
QUARANTINE_PATH = PROJECT_ROOT / "data" / "fincrm_quarantine.json"
API_BASE_URL = "http://127.0.0.1:8000"


def api_headers() -> dict[str, str]:
    token = st.session_state.get("api_token") if hasattr(st, "session_state") else None
    if token:
        return {"X-PRISM-TOKEN": str(token)}
    return {}


def set_sync_status(level: str, message: str) -> None:
    if not hasattr(st, "session_state"):
        return
    st.session_state["sync_status"] = {
        "level": level,
        "message": message,
        "updated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%SZ"),
    }


def clear_sync_status() -> None:
    if hasattr(st, "session_state"):
        st.session_state.pop("sync_status", None)


def _extract_error_detail(response: Any) -> str:
    try:
        payload = response.json()
        if isinstance(payload, dict):
            detail = payload.get("detail")
            if isinstance(detail, str):
                return detail
            if isinstance(detail, dict):
                message = detail.get("message")
                if isinstance(message, str):
                    return message
                return json.dumps(detail)
            return json.dumps(payload)
    except Exception:
        pass
    return response.text[:300] if getattr(response, "text", None) else "No response details"


def ensure_quarantine_dir_and_file() -> None:
    QUARANTINE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not QUARANTINE_PATH.exists():
        QUARANTINE_PATH.write_text("[]", encoding="utf-8")


def load_local_quarantine() -> list[dict[str, Any]]:
    ensure_quarantine_dir_and_file()
    try:
        parsed = json.loads(QUARANTINE_PATH.read_text(encoding="utf-8"))
        if isinstance(parsed, list):
            return [q for q in parsed if isinstance(q, dict)]
    except Exception:
        pass
    return []


def save_local_quarantine(quarantine_items: list[dict[str, Any]]) -> None:
    ensure_quarantine_dir_and_file()
    QUARANTINE_PATH.write_text(json.dumps(quarantine_items, indent=2), encoding="utf-8")


def add_quarantine_items(
    section_key: str,
    quarantine_items: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    reasons_by_row: list[list[str]],
) -> list[dict[str, Any]]:
    now = datetime.utcnow().isoformat() + "Z"
    added: list[dict[str, Any]] = []
    for row, reasons in zip(rows, reasons_by_row):
        item = {
            "id": str(uuid.uuid4()),
            "section": section_key,
            "row": row,
            "reasons": reasons,
            "imported_at": now,
        }
        quarantine_items.append(item)
        added.append(item)
    return added


def get_mock_data() -> dict[str, list[dict[str, Any]]]:
    return {
        "transactions": [
            {"date": "2026-03-01", "merchant": "Office Depot", "category": "Operations", "amount": -126.42},
            {"date": "2026-03-03", "merchant": "Client Invoice - ACME", "category": "Revenue", "amount": 3200.00},
            {"date": "2026-03-06", "merchant": "AWS", "category": "Infrastructure", "amount": -214.17},
            {"date": "2026-03-11", "merchant": "Client Invoice - Timberline", "category": "Revenue", "amount": 1850.00},
            {"date": "2026-03-14", "merchant": "Canva Pro", "category": "Software", "amount": -14.99},
        ],
        "contacts": [
            {"name": "Jamie Rivera", "company": "ACME Co", "email": "jamie@acme.example", "status": "Active"},
            {"name": "Avery Patel", "company": "Northline", "email": "avery@northline.example", "status": "Prospect"},
            {"name": "Casey Morgan", "company": "Timberline", "email": "casey@timberline.example", "status": "Active"},
            {"name": "Jordan Lee", "company": "Pioneer Labs", "email": "jordan@pioneer.example", "status": "Dormant"},
        ],
        "deals": [
            {"deal": "PRISM Retainer", "company": "ACME Co", "stage": "Won", "value": 12000},
            {"deal": "Ops Automation", "company": "Northline", "stage": "Proposal", "value": 6400},
            {"deal": "CRM Cleanup", "company": "Timberline", "stage": "Negotiation", "value": 4800},
            {"deal": "Analytics Pilot", "company": "Pioneer Labs", "stage": "Discovery", "value": 3500},
        ],
        "tasks": [
            {"task": "Send proposal update", "owner": "Tim", "due": "2026-03-20", "priority": "High", "done": False},
            {"task": "Review monthly spend", "owner": "Tim", "due": "2026-03-21", "priority": "Medium", "done": False},
            {"task": "Follow up with Avery", "owner": "Tim", "due": "2026-03-22", "priority": "High", "done": True},
        ],
    }


def ensure_data_dir() -> None:
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)


def load_local_data() -> dict[str, list[dict[str, Any]]]:
    ensure_data_dir()
    if not DATA_PATH.exists():
        data = get_mock_data()
        save_local_data(data)
        return _normalize_data(data)

    with DATA_PATH.open("r", encoding="utf-8") as f:
        return _normalize_data(json.load(f))


def save_local_data(data: dict[str, list[dict[str, Any]]]) -> None:
    ensure_data_dir()
    with DATA_PATH.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def to_csv_bytes(rows: list[dict[str, Any]]) -> bytes:
    if not rows:
        return b""
    headers = list(rows[0].keys())
    lines = [",".join(headers)]
    for row in rows:
        fields: list[str] = []
        for header in headers:
            value = str(row.get(header, ""))
            escaped = value.replace('"', '""')
            if "," in escaped or '"' in escaped:
                escaped = f'"{escaped}"'
            fields.append(escaped)
        lines.append(",".join(fields))
    return ("\n".join(lines) + "\n").encode("utf-8")


def parse_csv_text(csv_text: str) -> list[dict[str, str]]:
    lines = [line.strip() for line in csv_text.splitlines() if line.strip()]
    if not lines:
        return []
    headers = [h.strip() for h in lines[0].split(",")]
    rows: list[dict[str, str]] = []
    for line in lines[1:]:
        values = [v.strip() for v in line.split(",")]
        padded = values + [""] * (len(headers) - len(values))
        rows.append(dict(zip(headers, padded)))
    return rows


def load_data_from_api() -> dict[str, list[dict[str, Any]]] | None:
    if requests is None:
        set_sync_status("warning", "Backend sync unavailable: requests package is not installed.")
        return None
    try:
        response = requests.get(f"{API_BASE_URL}/data", timeout=3, headers=api_headers())
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict):
            set_sync_status("success", "Loaded latest data from FastAPI backend.")
            return _normalize_data(payload)
    except requests.HTTPError as exc:
        response = exc.response
        detail = _extract_error_detail(response) if response is not None else "Unknown HTTP error"
        status_code = response.status_code if response is not None else "unknown"
        set_sync_status("error", f"Failed to load data from backend ({status_code}): {detail}")
        return None
    except Exception as exc:
        set_sync_status("error", f"Failed to load data from backend: {exc}")
        return None
    return None


def save_data_to_api(data: dict[str, list[dict[str, Any]]]) -> bool:
    if requests is None:
        set_sync_status("warning", "Backend save skipped: requests package is not installed.")
        return False
    try:
        response = requests.put(f"{API_BASE_URL}/data", json=data, timeout=3, headers=api_headers())
        response.raise_for_status()
        set_sync_status("success", "Saved data to FastAPI backend.")
        return True
    except requests.HTTPError as exc:
        response = exc.response
        detail = _extract_error_detail(response) if response is not None else "Unknown HTTP error"
        status_code = response.status_code if response is not None else "unknown"
        set_sync_status("error", f"Backend save failed ({status_code}): {detail}")
        return False
    except Exception as exc:
        set_sync_status("error", f"Backend save failed: {exc}")
        return False


def load_quarantine_from_api() -> list[dict[str, Any]] | None:
    if requests is None:
        set_sync_status("warning", "Backend quarantine sync unavailable: requests package is not installed.")
        return None
    try:
        response = requests.get(f"{API_BASE_URL}/quarantine", timeout=3, headers=api_headers())
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, list):
            set_sync_status("success", "Loaded quarantine items from FastAPI backend.")
            return [q for q in payload if isinstance(q, dict)]
    except requests.HTTPError as exc:
        response = exc.response
        detail = _extract_error_detail(response) if response is not None else "Unknown HTTP error"
        status_code = response.status_code if response is not None else "unknown"
        set_sync_status("error", f"Failed to load quarantine from backend ({status_code}): {detail}")
        return None
    except Exception as exc:
        set_sync_status("error", f"Failed to load quarantine from backend: {exc}")
        return None
    return None


def append_quarantine_items_to_api(items: list[dict[str, Any]]) -> bool:
    if requests is None or not items:
        if items:
            set_sync_status("warning", "Quarantine sync skipped: requests package is not installed.")
        return False
    try:
        response = requests.post(
            f"{API_BASE_URL}/quarantine/items",
            json={"items": items},
            timeout=3,
            headers=api_headers(),
        )
        response.raise_for_status()
        set_sync_status("success", f"Synced {len(items)} quarantine item(s) to backend.")
        return True
    except requests.HTTPError as exc:
        response = exc.response
        detail = _extract_error_detail(response) if response is not None else "Unknown HTTP error"
        status_code = response.status_code if response is not None else "unknown"
        set_sync_status("error", f"Failed to sync quarantine items ({status_code}): {detail}")
        return False
    except Exception as exc:
        set_sync_status("error", f"Failed to sync quarantine items: {exc}")
        return False


def delete_quarantine_item_via_api(item_id: str) -> bool:
    if requests is None:
        set_sync_status("warning", "Backend quarantine delete skipped: requests package is not installed.")
        return False
    try:
        response = requests.delete(f"{API_BASE_URL}/quarantine/{item_id}", timeout=3, headers=api_headers())
        response.raise_for_status()
        set_sync_status("success", f"Deleted quarantine item {item_id} on backend.")
        return True
    except requests.HTTPError as exc:
        response = exc.response
        detail = _extract_error_detail(response) if response is not None else "Unknown HTTP error"
        status_code = response.status_code if response is not None else "unknown"
        set_sync_status("error", f"Failed to delete quarantine item on backend ({status_code}): {detail}")
        return False
    except Exception as exc:
        set_sync_status("error", f"Failed to delete quarantine item on backend: {exc}")
        return False


def persist_data(data: dict[str, list[dict[str, Any]]]) -> None:
    # Backend-first if connected, always mirrored locally as reliable fallback.
    if st.session_state.get("backend_mode"):
        backend_saved = save_data_to_api(data)
        if not backend_saved:
            set_sync_status("warning", "Saved locally; backend save failed. Check token, API availability, or payload errors.")
    save_local_data(data)


def render_data_tools(section: str, data: dict[str, list[dict[str, Any]]], numeric_keys: list[str] | None = None) -> None:
    numeric_keys = numeric_keys or []
    key = section.lower()
    rows = data[key]

    c1, c2 = st.columns(2)
    with c1:
        st.download_button(
            f"Export {section} CSV",
            data=to_csv_bytes(rows),
            file_name=f"{key}.csv",
            mime="text/csv",
        )
    with c2:
        upload = st.file_uploader(
            f"Import {section} CSV",
            type=["csv"],
            key=f"upload_{key}",
            help="CSV headers should match current column names.",
        )
        if upload is not None:
            try:
                parsed = parse_csv_text(upload.getvalue().decode("utf-8"))
                valid_rows: list[dict[str, Any]] = []
                invalid_rows: list[dict[str, Any]] = []
                invalid_reasons: list[list[str]] = []

                for row in parsed:
                    normalized, reasons = validate_row(key, dict(row))
                    if reasons:
                        invalid_rows.append(dict(row))
                        invalid_reasons.append(reasons)
                    else:
                        assert normalized is not None
                        valid_rows.append(normalized)

                # Durable behavior: never silently drop invalid rows.
                st.session_state.quarantine_items = st.session_state.get("quarantine_items", [])
                if invalid_rows:
                    new_items = add_quarantine_items(key, st.session_state.quarantine_items, invalid_rows, invalid_reasons)
                    save_local_quarantine(st.session_state.quarantine_items)
                    if st.session_state.get("backend_mode"):
                        append_quarantine_items_to_api(new_items)

                data[key] = valid_rows
                persist_data(data)

                if invalid_rows:
                    st.warning(
                        f"Imported {len(valid_rows)} {section.lower()} row(s), quarantined {len(invalid_rows)} invalid row(s)."
                    )
                else:
                    st.success(f"Imported {len(valid_rows)} {section.lower()} row(s).")
            except Exception as exc:
                st.error(f"Import failed: {exc}")


def render_overview(data: dict[str, list[dict[str, Any]]]) -> None:
    transactions = data["transactions"]
    deals = data["deals"]
    contacts = data["contacts"]
    tasks = data["tasks"]

    revenue = sum(
        (amt := _safe_float(t.get("amount"))) for t in transactions if (amt is not None and amt > 0)
    )
    expenses = sum(
        (-amt) for t in transactions if (amt := _safe_float(t.get("amount"))) is not None and amt < 0
    )
    pipeline = sum(
        (val := _safe_float(d.get("value"))) for d in deals if d.get("stage") != "Won" and (val is not None)
    )
    open_tasks = sum(1 for t in tasks if _parse_bool(t.get("done")) is False or (t.get("done") is None))
    active_contacts = sum(1 for c in contacts if c.get("status") == "Active")

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Revenue", f"${revenue:,.2f}")
    c2.metric("Expenses", f"${expenses:,.2f}")
    c3.metric("Pipeline", f"${pipeline:,.0f}")
    c4.metric("Open Tasks", open_tasks)
    c5.metric("Active Contacts", active_contacts)

    st.subheader("Quick Snapshot")
    st.dataframe(transactions, use_container_width=True, hide_index=True)


def render_transactions(data: dict[str, list[dict[str, Any]]]) -> None:
    st.subheader("Transactions")
    st.caption("Track cash in and cash out. Current values are mock data.")
    st.dataframe(data["transactions"], use_container_width=True, hide_index=True)

    with st.expander("Add mock transaction"):
        with st.form("add_tx"):
            tx_date = st.date_input("Date")
            merchant = st.text_input("Merchant")
            category = st.selectbox("Category", ALLOWED_CATEGORIES)
            amount = st.number_input("Amount", value=0.0, step=10.0)
            submit = st.form_submit_button("Add")
            if submit:
                candidate = {
                    "date": tx_date.isoformat(),
                    "merchant": merchant,
                    "category": category,
                    "amount": float(amount),
                }
                normalized, reasons = validate_row("transactions", candidate)
                if reasons:
                    st.error("Could not save transaction: " + "; ".join(reasons))
                else:
                    assert normalized is not None
                    data["transactions"].append(normalized)
                    persist_data(data)
                    st.success("Transaction saved.")
    render_data_tools("Transactions", data, numeric_keys=["amount"])


def render_contacts(data: dict[str, list[dict[str, Any]]]) -> None:
    st.subheader("Contacts")
    st.dataframe(data["contacts"], use_container_width=True, hide_index=True)

    with st.expander("Add mock contact"):
        with st.form("add_contact"):
            name = st.text_input("Name")
            company = st.text_input("Company")
            email = st.text_input("Email")
            status = st.selectbox("Status", ALLOWED_CONTACT_STATUSES)
            submit = st.form_submit_button("Add")
            if submit:
                candidate = {
                    "name": name,
                    "company": company,
                    "email": email,
                    "status": status,
                }
                normalized, reasons = validate_row("contacts", candidate)
                if reasons:
                    st.error("Could not save contact: " + "; ".join(reasons))
                else:
                    assert normalized is not None
                    data["contacts"].append(normalized)
                    persist_data(data)
                    st.success("Contact saved.")
    render_data_tools("Contacts", data)


def render_deals(data: dict[str, list[dict[str, Any]]]) -> None:
    st.subheader("Deals")
    st.dataframe(data["deals"], use_container_width=True, hide_index=True)

    stage_filter = st.multiselect(
        "Filter stages",
        ALLOWED_DEAL_STAGES,
        default=["Discovery", "Proposal", "Negotiation", "Won"],
    )
    filtered = [d for d in data["deals"] if d["stage"] in stage_filter]
    st.write(f"Showing {len(filtered)} deal(s)")
    st.dataframe(filtered, use_container_width=True, hide_index=True)
    render_data_tools("Deals", data, numeric_keys=["value"])


def render_tasks(data: dict[str, list[dict[str, Any]]]) -> None:
    st.subheader("Tasks")
    edited = st.data_editor(
        data["tasks"],
        use_container_width=True,
        hide_index=True,
        column_config={
            "done": st.column_config.CheckboxColumn("Done"),
            "priority": st.column_config.SelectboxColumn("Priority", options=ALLOWED_TASK_PRIORITIES),
        },
        key="tasks_editor",
    )
    if edited != data["tasks"]:
        valid_rows: list[dict[str, Any]] = []
        invalid_rows: list[dict[str, Any]] = []
        invalid_reasons: list[list[str]] = []

        for row in edited:
            normalized, reasons = validate_row("tasks", dict(row))
            if reasons:
                invalid_rows.append(dict(row))
                invalid_reasons.append(reasons)
            else:
                assert normalized is not None
                valid_rows.append(normalized)

        data["tasks"] = valid_rows
        persist_data(data)
        if invalid_rows:
            st.session_state.quarantine_items = st.session_state.get("quarantine_items", [])
            new_items = add_quarantine_items("tasks", st.session_state.quarantine_items, invalid_rows, invalid_reasons)
            save_local_quarantine(st.session_state.quarantine_items)
            if st.session_state.get("backend_mode"):
                append_quarantine_items_to_api(new_items)
            st.warning(f"Saved {len(valid_rows)} task(s). Quarantined {len(invalid_rows)} invalid row(s).")
        else:
            st.success("Tasks saved.")
    render_data_tools("Tasks", data)


def render_quarantine_page(mock_data: dict[str, list[dict[str, Any]]]) -> None:
    st.subheader("Quarantine (validation failures)")
    st.caption("Invalid imported/edited rows are stored here so they can be reviewed and restored safely.")

    quarantine_items: list[dict[str, Any]] = st.session_state.get("quarantine_items", [])
    if "quarantine_items" not in st.session_state:
        st.session_state.quarantine_items = quarantine_items

    section_label_map = {
        "transactions": "Transactions",
        "contacts": "Contacts",
        "deals": "Deals",
        "tasks": "Tasks",
    }
    section = st.selectbox("Section", ["transactions", "contacts", "deals", "tasks"], format_func=lambda s: section_label_map[s])
    items = [q for q in quarantine_items if q.get("section") == section]
    items = sorted(items, key=lambda q: q.get("imported_at", ""), reverse=True)

    st.write(f"{len(items)} quarantined item(s)")
    if not items:
        st.info("No quarantined items right now.")
        return

    preview_rows = []
    for it in items[:50]:
        reasons = it.get("reasons") or []
        preview_rows.append(
            {
                "id": it.get("id"),
                "imported_at": it.get("imported_at", ""),
                "reasons": "; ".join(reasons[:2]) + ("..." if len(reasons) > 2 else ""),
            }
        )
    st.dataframe(preview_rows, use_container_width=True, hide_index=True)

    selected_id = st.selectbox("Pick an item to restore", [it["id"] for it in items])
    selected = next((it for it in items if it["id"] == selected_id), None)
    if not selected:
        st.error("Selected item not found.")
        return

    row = selected.get("row", {}) or {}
    reasons = selected.get("reasons", []) or []
    st.warning("Reason(s): " + "; ".join(reasons))

    def safe_date_input_value(v: Any) -> date:
        parsed = _parse_iso_date_value(v)
        if parsed:
            try:
                return date.fromisoformat(parsed)
            except Exception:
                pass
        return date.today()

    with st.form(f"restore_form_{selected_id}"):
        if section == "transactions":
            tx_dt = st.date_input("date", value=safe_date_input_value(row.get("date")))
            merchant = st.text_input("merchant", value=str(row.get("merchant", "")))
            category = st.selectbox("category", ALLOWED_CATEGORIES, index=max(0, ALLOWED_CATEGORIES.index(row.get("category"))) if row.get("category") in ALLOWED_CATEGORIES else 0)
            amount = st.number_input("amount", value=_safe_float(row.get("amount")) or 0.0, step=10.0)
            submit_label = "Restore transaction"
            submitted = st.form_submit_button(submit_label)
            if submitted:
                candidate = {"date": tx_dt.isoformat(), "merchant": merchant, "category": category, "amount": float(amount)}
                normalized, row_reasons = validate_row("transactions", candidate)
                if row_reasons:
                    st.error("Still invalid: " + "; ".join(row_reasons))
                else:
                    assert normalized is not None
                    mock_data["transactions"].append(normalized)
                    st.session_state.quarantine_items = [it for it in st.session_state.quarantine_items if it.get("id") != selected_id]
                    persist_data(mock_data)
                    if st.session_state.get("backend_mode"):
                        if not delete_quarantine_item_via_api(selected_id):
                            st.warning("Restored locally, but failed to delete quarantine item on the backend (permissions or connectivity).")
                    save_local_quarantine(st.session_state.quarantine_items)
                    st.success("Restored.")
                    st.rerun()

        elif section == "contacts":
            name = st.text_input("name", value=str(row.get("name", "")))
            company = st.text_input("company", value=str(row.get("company", "")))
            email = st.text_input("email", value=str(row.get("email", "")))
            status = st.selectbox(
                "status",
                ALLOWED_CONTACT_STATUSES,
                index=max(0, ALLOWED_CONTACT_STATUSES.index(row.get("status"))) if row.get("status") in ALLOWED_CONTACT_STATUSES else 0,
            )
            submitted = st.form_submit_button("Restore contact")
            if submitted:
                candidate = {"name": name, "company": company, "email": email, "status": status}
                normalized, row_reasons = validate_row("contacts", candidate)
                if row_reasons:
                    st.error("Still invalid: " + "; ".join(row_reasons))
                else:
                    assert normalized is not None
                    mock_data["contacts"].append(normalized)
                    st.session_state.quarantine_items = [it for it in st.session_state.quarantine_items if it.get("id") != selected_id]
                    persist_data(mock_data)
                    if st.session_state.get("backend_mode"):
                        if not delete_quarantine_item_via_api(selected_id):
                            st.warning("Restored locally, but failed to delete quarantine item on the backend (permissions or connectivity).")
                    save_local_quarantine(st.session_state.quarantine_items)
                    st.success("Restored.")
                    st.rerun()

        elif section == "deals":
            deal = st.text_input("deal", value=str(row.get("deal", "")))
            company = st.text_input("company", value=str(row.get("company", "")))
            stage = st.selectbox(
                "stage",
                ALLOWED_DEAL_STAGES,
                index=max(0, ALLOWED_DEAL_STAGES.index(row.get("stage"))) if row.get("stage") in ALLOWED_DEAL_STAGES else 0,
            )
            value = st.number_input("value", value=_safe_float(row.get("value")) or 0.0, step=100.0)
            submitted = st.form_submit_button("Restore deal")
            if submitted:
                candidate = {"deal": deal, "company": company, "stage": stage, "value": float(value)}
                normalized, row_reasons = validate_row("deals", candidate)
                if row_reasons:
                    st.error("Still invalid: " + "; ".join(row_reasons))
                else:
                    assert normalized is not None
                    mock_data["deals"].append(normalized)
                    st.session_state.quarantine_items = [it for it in st.session_state.quarantine_items if it.get("id") != selected_id]
                    persist_data(mock_data)
                    if st.session_state.get("backend_mode"):
                        if not delete_quarantine_item_via_api(selected_id):
                            st.warning("Restored locally, but failed to delete quarantine item on the backend (permissions or connectivity).")
                    save_local_quarantine(st.session_state.quarantine_items)
                    st.success("Restored.")
                    st.rerun()

        elif section == "tasks":
            task = st.text_input("task", value=str(row.get("task", "")))
            owner = st.text_input("owner", value=str(row.get("owner", "")))
            due = st.date_input("due", value=safe_date_input_value(row.get("due")))
            priority = st.selectbox(
                "priority",
                ALLOWED_TASK_PRIORITIES,
                index=max(0, ALLOWED_TASK_PRIORITIES.index(row.get("priority"))) if row.get("priority") in ALLOWED_TASK_PRIORITIES else 0,
            )
            done_default = _parse_bool(row.get("done"))
            done = st.checkbox("done", value=bool(done_default) if done_default is not None else False)
            submitted = st.form_submit_button("Restore task")
            if submitted:
                candidate = {"task": task, "owner": owner, "due": due.isoformat(), "priority": priority, "done": bool(done)}
                normalized, row_reasons = validate_row("tasks", candidate)
                if row_reasons:
                    st.error("Still invalid: " + "; ".join(row_reasons))
                else:
                    assert normalized is not None
                    mock_data["tasks"].append(normalized)
                    st.session_state.quarantine_items = [it for it in st.session_state.quarantine_items if it.get("id") != selected_id]
                    persist_data(mock_data)
                    if st.session_state.get("backend_mode"):
                        if not delete_quarantine_item_via_api(selected_id):
                            st.warning("Restored locally, but failed to delete quarantine item on the backend (permissions or connectivity).")
                    save_local_quarantine(st.session_state.quarantine_items)
                    st.success("Restored.")
                    st.rerun()

    st.divider()
    if st.button("Delete quarantined item permanently", key=f"delete_{selected_id}"):
        if st.session_state.get("backend_mode"):
            if not delete_quarantine_item_via_api(selected_id):
                st.warning("Failed to delete quarantine item on the backend (permissions or connectivity). Local delete will still proceed.")
        st.session_state.quarantine_items = [it for it in st.session_state.quarantine_items if it.get("id") != selected_id]
        save_local_quarantine(st.session_state.quarantine_items)
        st.success("Deleted.")
        st.rerun()


def main() -> None:
    st.set_page_config(page_title="FinCRM Dashboard", layout="wide")
    st.title("FinCRM Dashboard")
    st.write("Usable mock prototype for finance + CRM workflow.")

    if "backend_mode" not in st.session_state:
        st.session_state.backend_mode = False
    if "api_token" not in st.session_state:
        st.session_state.api_token = ""

    with st.sidebar.expander("Storage Mode", expanded=True):
        backend_toggle = st.toggle("Use FastAPI backend", value=st.session_state.backend_mode)
        st.session_state.backend_mode = backend_toggle
        if not backend_toggle:
            clear_sync_status()
        st.session_state.api_token = st.text_input(
            "API token (optional)",
            value=st.session_state.api_token,
            type="password",
            help="Used for backend sync. If admin tokens are configured on the API, this token should be the admin token to restore/delete quarantined items.",
        )
        st.caption("Backend URL: http://127.0.0.1:8000")

    sync_status = st.session_state.get("sync_status")
    if isinstance(sync_status, dict):
        level = str(sync_status.get("level", "info"))
        message = str(sync_status.get("message", ""))
        timestamp = str(sync_status.get("updated_at", ""))
        if message:
            if level == "error":
                st.error(f"Sync status ({timestamp}): {message}")
            elif level == "warning":
                st.warning(f"Sync status ({timestamp}): {message}")
            elif level == "success":
                st.success(f"Sync status ({timestamp}): {message}")

    if "quarantine_items" not in st.session_state:
        if st.session_state.backend_mode:
            remote_quarantine = load_quarantine_from_api()
            st.session_state.quarantine_items = remote_quarantine if remote_quarantine else load_local_quarantine()
        else:
            st.session_state.quarantine_items = load_local_quarantine()

    if "mock_data" not in st.session_state:
        if st.session_state.backend_mode:
            remote_data = load_data_from_api()
            st.session_state.mock_data = remote_data if remote_data else load_local_data()
        else:
            st.session_state.mock_data = load_local_data()

    if st.sidebar.button("Reload Data"):
        if st.session_state.backend_mode:
            remote_data = load_data_from_api()
            st.session_state.mock_data = remote_data if remote_data else load_local_data()
            remote_quarantine = load_quarantine_from_api()
            st.session_state.quarantine_items = remote_quarantine if remote_quarantine else load_local_quarantine()
        else:
            st.session_state.mock_data = load_local_data()
            st.session_state.quarantine_items = load_local_quarantine()
        st.rerun()

    if st.sidebar.button("Save All Now"):
        persist_data(st.session_state.mock_data)
        save_local_quarantine(st.session_state.quarantine_items)
        st.sidebar.success("Saved.")

    st.sidebar.header("Navigation")
    page = st.sidebar.radio(
        "Go to",
        ["Overview", "Transactions", "Contacts", "Deals", "Tasks", "Quarantine"],
    )

    if page == "Overview":
        render_overview(st.session_state.mock_data)
    elif page == "Transactions":
        render_transactions(st.session_state.mock_data)
    elif page == "Contacts":
        render_contacts(st.session_state.mock_data)
    elif page == "Deals":
        render_deals(st.session_state.mock_data)
    elif page == "Tasks":
        render_tasks(st.session_state.mock_data)
    elif page == "Quarantine":
        render_quarantine_page(st.session_state.mock_data)


if __name__ == "__main__":
    main()