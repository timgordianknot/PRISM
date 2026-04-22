"""PRISM FinCRM dashboard.

Coherent implementation order:
1) Local JSON persistence.
2) CSV import/export utilities.
3) Optional FastAPI backend sync (fallback-safe).
"""

from __future__ import annotations

import csv
import io
import json
import uuid
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
from prism_storage import file_locks, read_json_file, save_json_unlocked, write_json_file

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = PROJECT_ROOT / "data" / "fincrm_data.json"
QUARANTINE_PATH = PROJECT_ROOT / "data" / "fincrm_quarantine.json"
API_BASE_URL = "http://127.0.0.1:8000"


def api_headers() -> dict[str, str]:
    token = st.session_state.get("api_token") if hasattr(st, "session_state") else None
    if token:
        return {"X-PRISM-TOKEN": str(token)}
    return {}


def _now_utc_label() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%SZ")


def set_sync_status(
    level: str,
    message: str,
    *,
    operation: str | None = None,
    retry_action: str | None = None,
    clear_retry: bool = False,
) -> None:
    if not hasattr(st, "session_state"):
        return
    st.session_state["sync_status"] = {
        "level": level,
        "message": message,
        "updated_at": _now_utc_label(),
        "operation": operation,
    }
    health = st.session_state.get("sync_health", {})
    if not isinstance(health, dict):
        health = {}
    health["last_operation"] = operation
    health["last_message"] = message
    health["last_level"] = level
    if level == "success":
        health["last_success_at"] = st.session_state["sync_status"]["updated_at"]
        health["last_success_message"] = message
    if level in {"warning", "error"}:
        health["last_error_at"] = st.session_state["sync_status"]["updated_at"]
        health["last_error_message"] = message
    st.session_state["sync_health"] = health

    if retry_action:
        st.session_state["sync_retry_action"] = retry_action
    elif clear_retry:
        st.session_state.pop("sync_retry_action", None)


def clear_sync_status() -> None:
    if hasattr(st, "session_state"):
        st.session_state.pop("sync_status", None)


def get_pending_backend_ops() -> dict[str, list[Any]]:
    pending = st.session_state.get("pending_backend_ops")
    if not isinstance(pending, dict):
        pending = {"quarantine_items": [], "delete_ids": []}
    quarantine_items = pending.get("quarantine_items")
    delete_ids = pending.get("delete_ids")
    normalized = {
        "quarantine_items": quarantine_items if isinstance(quarantine_items, list) else [],
        "delete_ids": delete_ids if isinstance(delete_ids, list) else [],
    }
    st.session_state["pending_backend_ops"] = normalized
    return normalized


def queue_pending_quarantine_items(items: list[dict[str, Any]]) -> None:
    if not items:
        return
    pending = get_pending_backend_ops()
    existing_ids = {str(item.get("id")) for item in pending["quarantine_items"] if isinstance(item, dict)}
    for item in items:
        if not isinstance(item, dict):
            continue
        item_id = str(item.get("id", ""))
        if item_id and item_id in existing_ids:
            continue
        pending["quarantine_items"].append(item)
        if item_id:
            existing_ids.add(item_id)
    st.session_state["pending_backend_ops"] = pending


def queue_pending_delete(item_id: str) -> None:
    pending = get_pending_backend_ops()
    if item_id not in pending["delete_ids"]:
        pending["delete_ids"].append(item_id)
    st.session_state["pending_backend_ops"] = pending


def sync_pending_backend_ops() -> bool:
    pending = get_pending_backend_ops()
    synced_any = False

    if pending["quarantine_items"]:
        if append_quarantine_items_to_api([item for item in pending["quarantine_items"] if isinstance(item, dict)]):
            pending["quarantine_items"] = []
            synced_any = True
        else:
            st.session_state["pending_backend_ops"] = pending
            return False

    if pending["delete_ids"]:
        remaining_delete_ids: list[str] = []
        for item_id in pending["delete_ids"]:
            if not delete_quarantine_item_via_api(item_id):
                remaining_delete_ids.append(item_id)
        pending["delete_ids"] = remaining_delete_ids
        if remaining_delete_ids:
            st.session_state["pending_backend_ops"] = pending
            return False
        synced_any = True

    st.session_state["pending_backend_ops"] = pending
    return synced_any or (not pending["quarantine_items"] and not pending["delete_ids"])


SYNC_RETRY_RELOAD = "reload_all"
SYNC_RETRY_SAVE_DATA = "save_data"
SYNC_RETRY_PENDING = "pending_ops"


def retry_last_sync_action() -> None:
    action = st.session_state.get("sync_retry_action")
    if not isinstance(action, str):
        set_sync_status("warning", "No retry action is currently available.")
        return

    if action == SYNC_RETRY_RELOAD:
        remote_data = load_data_from_api()
        if remote_data is not None:
            st.session_state.mock_data = remote_data
        else:
            st.session_state.mock_data = load_local_data()

        remote_quarantine = load_quarantine_from_api()
        if remote_quarantine is not None:
            st.session_state.quarantine_items = remote_quarantine
        else:
            st.session_state.quarantine_items = load_local_quarantine()
        return

    if action == SYNC_RETRY_SAVE_DATA:
        mock_data = st.session_state.get("mock_data")
        if isinstance(mock_data, dict):
            persist_data(mock_data)
            return
        set_sync_status("warning", "No in-memory dataset available to retry save.")
        return

    if action == SYNC_RETRY_PENDING:
        if sync_pending_backend_ops():
            set_sync_status(
                "success",
                "Successfully synced pending backend operations.",
                operation="pending_ops_sync",
                clear_retry=True,
            )
        else:
            set_sync_status(
                "warning",
                "Pending backend operations still need retry.",
                operation="pending_ops_sync",
                retry_action=SYNC_RETRY_PENDING,
            )
        return

    set_sync_status("warning", f"Unsupported retry action: {action}")


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


def load_local_quarantine() -> list[dict[str, Any]]:
    parsed = read_json_file(QUARANTINE_PATH, default_factory=list)
    if isinstance(parsed, list):
        return [q for q in parsed if isinstance(q, dict)]
    return []


def save_local_quarantine(quarantine_items: list[dict[str, Any]]) -> None:
    write_json_file(QUARANTINE_PATH, [q for q in quarantine_items if isinstance(q, dict)])


def save_local_data_and_quarantine(
    data: dict[str, list[dict[str, Any]]],
    quarantine_items: list[dict[str, Any]],
) -> None:
    with file_locks([DATA_PATH, QUARANTINE_PATH]):
        save_json_unlocked(DATA_PATH, _normalize_data(data))
        save_json_unlocked(QUARANTINE_PATH, [q for q in quarantine_items if isinstance(q, dict)])


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


def load_local_data() -> dict[str, list[dict[str, Any]]]:
    payload = read_json_file(DATA_PATH, default_factory=get_mock_data)
    return _normalize_data(payload)


def save_local_data(data: dict[str, list[dict[str, Any]]]) -> None:
    write_json_file(DATA_PATH, _normalize_data(data))


def to_csv_bytes(rows: list[dict[str, Any]]) -> bytes:
    if not rows:
        return b""
    headers: list[str] = []
    for row in rows:
        for key in row.keys():
            if key not in headers:
                headers.append(key)

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=headers, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({header: row.get(header, "") for header in headers})
    return output.getvalue().encode("utf-8")


def parse_csv_text(csv_text: str) -> list[dict[str, str]]:
    if not csv_text.strip():
        return []
    reader = csv.DictReader(io.StringIO(csv_text))
    if reader.fieldnames is None:
        return []
    rows: list[dict[str, str]] = []
    for row in reader:
        if not isinstance(row, dict):
            continue
        normalized: dict[str, str] = {}
        for key, value in row.items():
            if key is None:
                continue
            normalized[str(key).strip()] = "" if value is None else str(value).strip()
        if any(value != "" for value in normalized.values()):
            rows.append(normalized)
    return rows


def load_data_from_api() -> dict[str, list[dict[str, Any]]] | None:
    if requests is None:
        set_sync_status(
            "warning",
            "Backend sync unavailable: requests package is not installed.",
            operation="load_data",
            retry_action=SYNC_RETRY_RELOAD,
        )
        return None
    try:
        response = requests.get(f"{API_BASE_URL}/data", timeout=3, headers=api_headers())
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict):
            set_sync_status("success", "Loaded latest data from FastAPI backend.", operation="load_data", clear_retry=True)
            return _normalize_data(payload)
    except requests.HTTPError as exc:
        response = exc.response
        detail = _extract_error_detail(response) if response is not None else "Unknown HTTP error"
        status_code = response.status_code if response is not None else "unknown"
        set_sync_status(
            "error",
            f"Failed to load data from backend ({status_code}): {detail}",
            operation="load_data",
            retry_action=SYNC_RETRY_RELOAD,
        )
        return None
    except Exception as exc:
        set_sync_status("error", f"Failed to load data from backend: {exc}", operation="load_data", retry_action=SYNC_RETRY_RELOAD)
        return None
    return None


def save_data_to_api(data: dict[str, list[dict[str, Any]]]) -> bool:
    if requests is None:
        set_sync_status(
            "warning",
            "Backend save skipped: requests package is not installed.",
            operation="save_data",
            retry_action=SYNC_RETRY_SAVE_DATA,
        )
        return False
    try:
        response = requests.put(f"{API_BASE_URL}/data", json=data, timeout=3, headers=api_headers())
        response.raise_for_status()
        set_sync_status("success", "Saved data to FastAPI backend.", operation="save_data", clear_retry=True)
        return True
    except requests.HTTPError as exc:
        response = exc.response
        detail = _extract_error_detail(response) if response is not None else "Unknown HTTP error"
        status_code = response.status_code if response is not None else "unknown"
        set_sync_status(
            "error",
            f"Backend save failed ({status_code}): {detail}",
            operation="save_data",
            retry_action=SYNC_RETRY_SAVE_DATA,
        )
        return False
    except Exception as exc:
        set_sync_status("error", f"Backend save failed: {exc}", operation="save_data", retry_action=SYNC_RETRY_SAVE_DATA)
        return False


def load_quarantine_from_api() -> list[dict[str, Any]] | None:
    if requests is None:
        set_sync_status(
            "warning",
            "Backend quarantine sync unavailable: requests package is not installed.",
            operation="load_quarantine",
            retry_action=SYNC_RETRY_RELOAD,
        )
        return None
    try:
        response = requests.get(f"{API_BASE_URL}/quarantine", timeout=3, headers=api_headers())
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, list):
            set_sync_status(
                "success",
                "Loaded quarantine items from FastAPI backend.",
                operation="load_quarantine",
                clear_retry=True,
            )
            return [q for q in payload if isinstance(q, dict)]
    except requests.HTTPError as exc:
        response = exc.response
        detail = _extract_error_detail(response) if response is not None else "Unknown HTTP error"
        status_code = response.status_code if response is not None else "unknown"
        set_sync_status(
            "error",
            f"Failed to load quarantine from backend ({status_code}): {detail}",
            operation="load_quarantine",
            retry_action=SYNC_RETRY_RELOAD,
        )
        return None
    except Exception as exc:
        set_sync_status(
            "error",
            f"Failed to load quarantine from backend: {exc}",
            operation="load_quarantine",
            retry_action=SYNC_RETRY_RELOAD,
        )
        return None
    return None


def append_quarantine_items_to_api(items: list[dict[str, Any]]) -> bool:
    if requests is None or not items:
        if items:
            set_sync_status(
                "warning",
                "Quarantine sync skipped: requests package is not installed.",
                operation="append_quarantine",
                retry_action=SYNC_RETRY_PENDING,
            )
        return False
    try:
        response = requests.post(
            f"{API_BASE_URL}/quarantine/items",
            json={"items": items},
            timeout=3,
            headers=api_headers(),
        )
        response.raise_for_status()
        set_sync_status(
            "success",
            f"Synced {len(items)} quarantine item(s) to backend.",
            operation="append_quarantine",
            clear_retry=True,
        )
        return True
    except requests.HTTPError as exc:
        response = exc.response
        detail = _extract_error_detail(response) if response is not None else "Unknown HTTP error"
        status_code = response.status_code if response is not None else "unknown"
        set_sync_status(
            "error",
            f"Failed to sync quarantine items ({status_code}): {detail}",
            operation="append_quarantine",
            retry_action=SYNC_RETRY_PENDING,
        )
        return False
    except Exception as exc:
        set_sync_status(
            "error",
            f"Failed to sync quarantine items: {exc}",
            operation="append_quarantine",
            retry_action=SYNC_RETRY_PENDING,
        )
        return False


def delete_quarantine_item_via_api(item_id: str) -> bool:
    if requests is None:
        set_sync_status(
            "warning",
            "Backend quarantine delete skipped: requests package is not installed.",
            operation="delete_quarantine",
            retry_action=SYNC_RETRY_PENDING,
        )
        return False
    try:
        response = requests.delete(f"{API_BASE_URL}/quarantine/{item_id}", timeout=3, headers=api_headers())
        response.raise_for_status()
        set_sync_status(
            "success",
            f"Deleted quarantine item {item_id} on backend.",
            operation="delete_quarantine",
            clear_retry=True,
        )
        return True
    except requests.HTTPError as exc:
        response = exc.response
        detail = _extract_error_detail(response) if response is not None else "Unknown HTTP error"
        status_code = response.status_code if response is not None else "unknown"
        set_sync_status(
            "error",
            f"Failed to delete quarantine item on backend ({status_code}): {detail}",
            operation="delete_quarantine",
            retry_action=SYNC_RETRY_PENDING,
        )
        return False
    except Exception as exc:
        set_sync_status(
            "error",
            f"Failed to delete quarantine item on backend: {exc}",
            operation="delete_quarantine",
            retry_action=SYNC_RETRY_PENDING,
        )
        return False


def persist_data(data: dict[str, list[dict[str, Any]]]) -> None:
    if st.session_state.get("backend_mode"):
        backend_saved = save_data_to_api(data)
        if not backend_saved:
            set_sync_status(
                "warning",
                "Saved locally; backend save failed. Check token, API availability, or payload errors.",
                operation="save_data",
                retry_action=SYNC_RETRY_SAVE_DATA,
            )
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

                st.session_state.quarantine_items = st.session_state.get("quarantine_items", [])
                if invalid_rows:
                    new_items = add_quarantine_items(key, st.session_state.quarantine_items, invalid_rows, invalid_reasons)
                    if st.session_state.get("backend_mode"):
                        if not append_quarantine_items_to_api(new_items):
                            queue_pending_quarantine_items(new_items)
                    save_local_quarantine(st.session_state.quarantine_items)

                data[key] = valid_rows
                persist_data(data)

                if invalid_rows:
                    st.warning(
                        f"Imported {len(valid_rows)} {section.lower()} row(s), "
                        f"quarantined {len(invalid_rows)} invalid row(s)."
                    )
                    preview_errors = [
                        f"row {idx + 1}: {', '.join(reason_list)}"
                        for idx, reason_list in enumerate(invalid_reasons[:3])
                    ]
                    st.caption("Sample validation errors: " + " | ".join(preview_errors))
                else:
                    st.success(f"Imported {len(valid_rows)} {section.lower()} row(s).")
            except Exception as exc:
                st.error(f"Import failed: {exc}")


def render_overview(data: dict[str, list[dict[str, Any]]]) -> None:
    transactions = data["transactions"]
    deals = data["deals"]
    contacts = data["contacts"]
    tasks = data["tasks"]

    revenue = sum((amt := _safe_float(t.get("amount"))) for t in transactions if (amt is not None and amt > 0))
    expenses = sum((-amt) for t in transactions if (amt := _safe_float(t.get("amount"))) is not None and amt < 0)
    pipeline = sum((val := _safe_float(d.get("value"))) for d in deals if d.get("stage") != "Won" and (val is not None))
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
            if st.session_state.get("backend_mode"):
                if not append_quarantine_items_to_api(new_items):
                    queue_pending_quarantine_items(new_items)
            save_local_quarantine(st.session_state.quarantine_items)
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
            submitted = st.form_submit_button("Restore transaction")
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
                            queue_pending_delete(selected_id)
                            st.warning("Restored locally; backend delete queued for retry.")
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
                            queue_pending_delete(selected_id)
                            st.warning("Restored locally; backend delete queued for retry.")
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
                            queue_pending_delete(selected_id)
                            st.warning("Restored locally; backend delete queued for retry.")
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
                            queue_pending_delete(selected_id)
                            st.warning("Restored locally; backend delete queued for retry.")
                    save_local_quarantine(st.session_state.quarantine_items)
                    st.success("Restored.")
                    st.rerun()

    st.divider()
    if st.button("Delete quarantined item permanently", key=f"delete_{selected_id}"):
        if st.session_state.get("backend_mode"):
            if not delete_quarantine_item_via_api(selected_id):
                queue_pending_delete(selected_id)
                st.warning("Backend delete failed; queued for retry. Local delete will proceed.")
        st.session_state.quarantine_items = [it for it in st.session_state.quarantine_items if it.get("id") != selected_id]
        save_local_quarantine(st.session_state.quarantine_items)
        st.success("Deleted.")
        st.rerun()


def render_sync_health() -> None:
    sync_status = st.session_state.get("sync_status")
    if isinstance(sync_status, dict):
        level = str(sync_status.get("level", "info"))
        message = str(sync_status.get("message", ""))
        timestamp = str(sync_status.get("updated_at", ""))
        if message:
            label = f"Sync status ({timestamp}): {message}"
            if level == "error":
                st.error(label)
            elif level == "warning":
                st.warning(label)
            elif level == "success":
                st.success(label)
            else:
                st.info(label)

    health = st.session_state.get("sync_health")
    if isinstance(health, dict):
        last_success_at = str(health.get("last_success_at", "") or "")
        last_error_at = str(health.get("last_error_at", "") or "")
        if last_success_at or last_error_at:
            summary_parts: list[str] = []
            if last_success_at:
                summary_parts.append(f"Last success: {last_success_at}")
            if last_error_at:
                summary_parts.append(f"Last issue: {last_error_at}")
            st.caption(" | ".join(summary_parts))


def initialize_page_state() -> None:
    if "backend_mode" not in st.session_state:
        st.session_state.backend_mode = False
    if "api_token" not in st.session_state:
        st.session_state.api_token = ""
    if "pending_backend_ops" not in st.session_state:
        st.session_state.pending_backend_ops = {"quarantine_items": [], "delete_ids": []}


def initialize_page_data() -> None:
    if "quarantine_items" not in st.session_state:
        if st.session_state.backend_mode:
            remote_quarantine = load_quarantine_from_api()
            st.session_state.quarantine_items = remote_quarantine if remote_quarantine is not None else load_local_quarantine()
        else:
            st.session_state.quarantine_items = load_local_quarantine()

    if "mock_data" not in st.session_state:
        if st.session_state.backend_mode:
            remote_data = load_data_from_api()
            st.session_state.mock_data = remote_data if remote_data is not None else load_local_data()
        else:
            st.session_state.mock_data = load_local_data()


def reload_from_sources() -> None:
    if st.session_state.backend_mode:
        remote_data = load_data_from_api()
        st.session_state.mock_data = remote_data if remote_data is not None else load_local_data()
        remote_quarantine = load_quarantine_from_api()
        st.session_state.quarantine_items = remote_quarantine if remote_quarantine is not None else load_local_quarantine()
    else:
        st.session_state.mock_data = load_local_data()
        st.session_state.quarantine_items = load_local_quarantine()


def main() -> None:
    st.set_page_config(page_title="FinCRM Dashboard", layout="wide")
    st.title("FinCRM Dashboard")
    st.write("Usable mock prototype for finance + CRM workflow.")
    initialize_page_state()

    with st.sidebar.expander("Storage Mode", expanded=True):
        backend_toggle = st.toggle("Use FastAPI backend", value=st.session_state.backend_mode)
        st.session_state.backend_mode = backend_toggle
        if not backend_toggle:
            clear_sync_status()
        st.session_state.api_token = st.text_input(
            "API token (optional)",
            value=st.session_state.api_token,
            type="password",
            help=(
                "Used for backend sync. If admin tokens are configured on the API, "
                "this token should be the admin token to restore/delete quarantined items."
            ),
        )
        st.caption("Backend URL: http://127.0.0.1:8000")

        if st.button("Retry last backend operation"):
            retry_last_sync_action()
            st.rerun()

    render_sync_health()
    initialize_page_data()

    pending_ops = get_pending_backend_ops()
    pending_count = len(pending_ops["quarantine_items"]) + len(pending_ops["delete_ids"])
    if pending_count > 0:
        st.info(
            "Pending backend sync items: "
            f"{len(pending_ops['quarantine_items'])} quarantine append(s), "
            f"{len(pending_ops['delete_ids'])} delete(s)."
        )
        if st.button("Retry pending backend queue"):
            if sync_pending_backend_ops():
                set_sync_status(
                    "success",
                    "Pending backend queue synced successfully.",
                    operation="pending_ops_sync",
                    clear_retry=True,
                )
            else:
                set_sync_status(
                    "warning",
                    "Pending backend queue still has failures.",
                    operation="pending_ops_sync",
                    retry_action=SYNC_RETRY_PENDING,
                )
            st.rerun()

    if st.sidebar.button("Reload Data"):
        reload_from_sources()
        st.rerun()

    if st.sidebar.button("Save All Now"):
        persist_data(st.session_state.mock_data)
        save_local_data_and_quarantine(st.session_state.mock_data, st.session_state.quarantine_items)
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
