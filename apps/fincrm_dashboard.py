"""PRISM FinCRM dashboard.

Coherent implementation order:
1) Local JSON persistence.
2) CSV import/export utilities.
3) Optional FastAPI backend sync (fallback-safe).
"""

from __future__ import annotations

import re
import uuid
import json
import csv
from io import StringIO
from datetime import date, datetime
from pathlib import Path
from typing import Any

import streamlit as st

try:
    import requests
except ImportError:
    requests = None

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = PROJECT_ROOT / "data" / "fincrm_data.json"
QUARANTINE_PATH = PROJECT_ROOT / "data" / "fincrm_quarantine.json"
API_BASE_URL = "http://127.0.0.1:8000"

ALLOWED_CATEGORIES = ["Revenue", "Operations", "Infrastructure", "Software", "Other"]
ALLOWED_CONTACT_STATUSES = ["Prospect", "Active", "Dormant"]
ALLOWED_DEAL_STAGES = ["Discovery", "Proposal", "Negotiation", "Won", "Lost"]
ALLOWED_TASK_PRIORITIES = ["Low", "Medium", "High"]
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def api_headers() -> dict[str, str]:
    token = st.session_state.get("api_token") if hasattr(st, "session_state") else None
    if token:
        return {"X-PRISM-TOKEN": str(token)}
    return {}


def _safe_float(v: Any) -> float | None:
    try:
        if v is None:
            return None
        if isinstance(v, bool):
            return float(int(v))
        s = str(v).strip().replace("$", "").replace(",", "")
        if s == "":
            return None
        return float(s)
    except Exception:
        return None


def _parse_bool(v: Any) -> bool | None:
    if isinstance(v, bool):
        return v
    if v is None:
        return None
    s = str(v).strip().lower()
    if s in {"true", "1", "yes", "y"}:
        return True
    if s in {"false", "0", "no", "n"}:
        return False
    return None


def _parse_iso_date_value(v: Any) -> str | None:
    try:
        if isinstance(v, datetime):
            return v.date().isoformat()
        if isinstance(v, date):
            return v.isoformat()
        if v is None:
            return None
        s = str(v).strip()
        if s == "":
            return None
        return date.fromisoformat(s).isoformat()
    except Exception:
        return None


def _normalize_data(data: Any) -> dict[str, list[dict[str, Any]]]:
    # Ensure schema shape exists so UI doesn't crash on missing keys.
    normalized: dict[str, list[dict[str, Any]]] = {
        "transactions": [],
        "contacts": [],
        "deals": [],
        "tasks": [],
    }
    if not isinstance(data, dict):
        return normalized
    for key in normalized.keys():
        if isinstance(data.get(key), list):
            normalized[key] = [r for r in data[key] if isinstance(r, dict)]
    return normalized


def _validate_transaction_row(row: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    tx_date = _parse_iso_date_value(row.get("date"))
    if not tx_date:
        errors.append("date must be YYYY-MM-DD")

    merchant = str(row.get("merchant", "")).strip()
    if not merchant:
        errors.append("merchant is required")

    category = str(row.get("category", "")).strip()
    if category not in ALLOWED_CATEGORIES:
        errors.append(f"category must be one of {ALLOWED_CATEGORIES}")

    amount = _safe_float(row.get("amount"))
    if amount is None:
        errors.append("amount must be a number")

    if errors:
        return None, errors
    return {
        "date": tx_date,
        "merchant": merchant,
        "category": category,
        "amount": float(amount),
    }, []


def _validate_contact_row(row: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    name = str(row.get("name", "")).strip()
    if not name:
        errors.append("name is required")

    company = str(row.get("company", "")).strip()
    if not company:
        errors.append("company is required")

    email = str(row.get("email", "")).strip().lower()
    if not email or not EMAIL_RE.match(email):
        errors.append("email must look like an email address")

    status = str(row.get("status", "")).strip()
    if status not in ALLOWED_CONTACT_STATUSES:
        errors.append(f"status must be one of {ALLOWED_CONTACT_STATUSES}")

    if errors:
        return None, errors
    return {"name": name, "company": company, "email": email, "status": status}, []


def _validate_deal_row(row: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    deal = str(row.get("deal", "")).strip()
    if not deal:
        errors.append("deal is required")

    company = str(row.get("company", "")).strip()
    if not company:
        errors.append("company is required")

    stage = str(row.get("stage", "")).strip()
    if stage not in ALLOWED_DEAL_STAGES:
        errors.append(f"stage must be one of {ALLOWED_DEAL_STAGES}")

    value = _safe_float(row.get("value"))
    if value is None:
        errors.append("value must be a number")

    if errors:
        return None, errors
    return {"deal": deal, "company": company, "stage": stage, "value": float(value)}, []


def _validate_task_row(row: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    task = str(row.get("task", "")).strip()
    if not task:
        errors.append("task is required")

    owner = str(row.get("owner", "")).strip()
    if not owner:
        errors.append("owner is required")

    due = _parse_iso_date_value(row.get("due"))
    if not due:
        errors.append("due must be YYYY-MM-DD")

    priority = str(row.get("priority", "")).strip()
    if priority not in ALLOWED_TASK_PRIORITIES:
        errors.append(f"priority must be one of {ALLOWED_TASK_PRIORITIES}")

    done = _parse_bool(row.get("done"))
    if done is None:
        errors.append("done must be boolean-like (true/false)")

    if errors:
        return None, errors
    return {"task": task, "owner": owner, "due": due, "priority": priority, "done": bool(done)}, []


def validate_row(section_key: str, row: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    if section_key == "transactions":
        return _validate_transaction_row(row)
    if section_key == "contacts":
        return _validate_contact_row(row)
    if section_key == "deals":
        return _validate_deal_row(row)
    if section_key == "tasks":
        return _validate_task_row(row)
    return None, [f"Unknown section: {section_key}"]


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

    try:
        with DATA_PATH.open("r", encoding="utf-8") as f:
            parsed = json.load(f)
        if not isinstance(parsed, dict):
            raise ValueError("Main data JSON must be an object at the root.")
        return _normalize_data(parsed)
    except Exception:
        # Preserve unreadable content for manual recovery, then heal with mock defaults.
        try:
            backup_path = DATA_PATH.with_name(f"{DATA_PATH.stem}.corrupt.json")
            backup_path.write_text(DATA_PATH.read_text(encoding="utf-8"), encoding="utf-8")
        except Exception:
            pass
        data = get_mock_data()
        save_local_data(data)
        return _normalize_data(data)


def save_local_data(data: dict[str, list[dict[str, Any]]]) -> None:
    ensure_data_dir()
    with DATA_PATH.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def to_csv_bytes(rows: list[dict[str, Any]]) -> bytes:
    if not rows:
        return b""
    headers = list(rows[0].keys())
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=headers, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: row.get(k, "") for k in headers})
    return output.getvalue().encode("utf-8")


def parse_csv_text(csv_text: str) -> list[dict[str, str]]:
    if not csv_text.strip():
        return []

    reader = csv.DictReader(StringIO(csv_text))
    if reader.fieldnames is None:
        return []

    normalized_headers = [str(h).strip() if h is not None else "" for h in reader.fieldnames]
    rows: list[dict[str, str]] = []
    for row in reader:
        parsed: dict[str, str] = {}
        for original_header, normalized_header in zip(reader.fieldnames, normalized_headers):
            key = normalized_header or ""
            value = row.get(original_header, "")
            parsed[key] = "" if value is None else str(value).strip()
        rows.append(parsed)
    return rows


def load_data_from_api() -> dict[str, list[dict[str, Any]]] | None:
    if requests is None:
        return None
    try:
        response = requests.get(f"{API_BASE_URL}/data", timeout=3, headers=api_headers())
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict):
            return _normalize_data(payload)
    except Exception:
        return None
    return None


def save_data_to_api(data: dict[str, list[dict[str, Any]]]) -> bool:
    if requests is None:
        return False
    try:
        response = requests.put(f"{API_BASE_URL}/data", json=data, timeout=3, headers=api_headers())
        response.raise_for_status()
        return True
    except Exception:
        return False


def load_quarantine_from_api() -> list[dict[str, Any]] | None:
    if requests is None:
        return None
    try:
        response = requests.get(f"{API_BASE_URL}/quarantine", timeout=3, headers=api_headers())
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, list):
            return [q for q in payload if isinstance(q, dict)]
    except Exception:
        return None
    return None


def append_quarantine_items_to_api(items: list[dict[str, Any]]) -> bool:
    if requests is None or not items:
        return False
    try:
        response = requests.post(
            f"{API_BASE_URL}/quarantine/items",
            json={"items": items},
            timeout=3,
            headers=api_headers(),
        )
        response.raise_for_status()
        return True
    except Exception:
        return False


def delete_quarantine_item_via_api(item_id: str) -> bool:
    if requests is None:
        return False
    try:
        response = requests.delete(f"{API_BASE_URL}/quarantine/{item_id}", timeout=3, headers=api_headers())
        response.raise_for_status()
        return True
    except Exception:
        return False


def persist_data(data: dict[str, list[dict[str, Any]]]) -> None:
    # Backend-first if connected, always mirrored locally as reliable fallback.
    if st.session_state.get("backend_mode"):
        save_data_to_api(data)
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

    revenue = 0.0
    for t in transactions:
        amt = _safe_float(t.get("amount"))
        if amt is not None and amt > 0:
            revenue += amt

    expenses = sum(
        (-amt) for t in transactions if (amt := _safe_float(t.get("amount"))) is not None and amt < 0
    )

    pipeline = 0.0
    for d in deals:
        val = _safe_float(d.get("value"))
        if d.get("stage") != "Won" and val is not None:
            pipeline += val

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
            category = st.selectbox("Category", ["Revenue", "Operations", "Infrastructure", "Software", "Other"])
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
            status = st.selectbox("Status", ["Prospect", "Active", "Dormant"])
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
        ["Discovery", "Proposal", "Negotiation", "Won", "Lost"],
        default=["Discovery", "Proposal", "Negotiation", "Won"],
    )
    filtered = [d for d in data["deals"] if d.get("stage") in stage_filter]
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
            "priority": st.column_config.SelectboxColumn("Priority", options=["Low", "Medium", "High"]),
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
        st.session_state.api_token = st.text_input(
            "API token (optional)",
            value=st.session_state.api_token,
            type="password",
            help="Used for backend sync. If admin tokens are configured on the API, this token should be the admin token to restore/delete quarantined items.",
        )
        st.caption("Backend URL: http://127.0.0.1:8000")

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