from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

SECTION_KEYS = ("transactions", "contacts", "deals", "tasks")

ALLOWED_CATEGORIES = ["Revenue", "Operations", "Infrastructure", "Software", "Other"]
ALLOWED_CONTACT_STATUSES = ["Prospect", "Active", "Dormant"]
ALLOWED_DEAL_STAGES = ["Discovery", "Proposal", "Negotiation", "Won", "Lost"]
ALLOWED_TASK_PRIORITIES = ["Low", "Medium", "High"]

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        if isinstance(value, bool):
            return float(int(value))
        serialized = str(value).strip().replace("$", "").replace(",", "")
        if serialized == "":
            return None
        return float(serialized)
    except Exception:
        return None


def parse_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    serialized = str(value).strip().lower()
    if serialized in {"true", "1", "yes", "y"}:
        return True
    if serialized in {"false", "0", "no", "n"}:
        return False
    return None


def parse_iso_date_value(value: Any) -> str | None:
    try:
        if isinstance(value, datetime):
            return value.date().isoformat()
        if isinstance(value, date):
            return value.isoformat()
        if value is None:
            return None
        serialized = str(value).strip()
        if serialized == "":
            return None
        return date.fromisoformat(serialized).isoformat()
    except Exception:
        return None


def normalize_data(data: Any) -> dict[str, list[dict[str, Any]]]:
    normalized: dict[str, list[dict[str, Any]]] = {key: [] for key in SECTION_KEYS}
    if not isinstance(data, dict):
        return normalized
    for key in SECTION_KEYS:
        rows = data.get(key)
        if isinstance(rows, list):
            normalized[key] = [row for row in rows if isinstance(row, dict)]
    return normalized


def validate_transaction_row(row: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    tx_date = parse_iso_date_value(row.get("date"))
    if not tx_date:
        errors.append("date must be YYYY-MM-DD")

    merchant = str(row.get("merchant", "")).strip()
    if not merchant:
        errors.append("merchant is required")

    category = str(row.get("category", "")).strip()
    if category not in ALLOWED_CATEGORIES:
        errors.append(f"category must be one of {ALLOWED_CATEGORIES}")

    amount = safe_float(row.get("amount"))
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


def validate_contact_row(row: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
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


def validate_deal_row(row: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
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

    deal_value = safe_float(row.get("value"))
    if deal_value is None:
        errors.append("value must be a number")

    if errors:
        return None, errors
    return {"deal": deal, "company": company, "stage": stage, "value": float(deal_value)}, []


def validate_task_row(row: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    task = str(row.get("task", "")).strip()
    if not task:
        errors.append("task is required")

    owner = str(row.get("owner", "")).strip()
    if not owner:
        errors.append("owner is required")

    due = parse_iso_date_value(row.get("due"))
    if not due:
        errors.append("due must be YYYY-MM-DD")

    priority = str(row.get("priority", "")).strip()
    if priority not in ALLOWED_TASK_PRIORITIES:
        errors.append(f"priority must be one of {ALLOWED_TASK_PRIORITIES}")

    done = parse_bool(row.get("done"))
    if done is None:
        errors.append("done must be boolean-like (true/false)")

    if errors:
        return None, errors
    return {"task": task, "owner": owner, "due": due, "priority": priority, "done": bool(done)}, []


def validate_row(section_key: str, row: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    if section_key == "transactions":
        return validate_transaction_row(row)
    if section_key == "contacts":
        return validate_contact_row(row)
    if section_key == "deals":
        return validate_deal_row(row)
    if section_key == "tasks":
        return validate_task_row(row)
    return None, [f"Unknown section: {section_key}"]


def validate_dataset(data: Any) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    normalized = normalize_data(data)
    issues: list[dict[str, Any]] = []
    if not isinstance(data, dict):
        issues.append({"section": None, "index": None, "errors": ["payload must be a JSON object"]})
        return normalized, issues

    for section in SECTION_KEYS:
        rows = data.get(section)
        if not isinstance(rows, list):
            issues.append(
                {
                    "section": section,
                    "index": None,
                    "errors": [f"{section} must be a list of objects"],
                }
            )
            continue

        validated_rows: list[dict[str, Any]] = []
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                issues.append({"section": section, "index": index, "errors": ["row must be an object"]})
                continue
            validated_row, row_errors = validate_row(section, row)
            if row_errors:
                issues.append({"section": section, "index": index, "errors": row_errors})
                continue
            assert validated_row is not None
            validated_rows.append(validated_row)
        normalized[section] = validated_rows

    return normalized, issues
