from __future__ import annotations

import os
import json
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel

APP_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = APP_ROOT / "data" / "fincrm_data.json"
QUARANTINE_PATH = APP_ROOT / "data" / "fincrm_quarantine.json"

app = FastAPI(title="PRISM FinCRM API", version="0.1.0")


class DataPayload(BaseModel):
    transactions: list[dict[str, Any]]
    contacts: list[dict[str, Any]]
    deals: list[dict[str, Any]]
    tasks: list[dict[str, Any]]


def default_data() -> dict[str, list[dict[str, Any]]]:
    return {
        "transactions": [
            {"date": "2026-03-01", "merchant": "Office Depot", "category": "Operations", "amount": -126.42},
            {"date": "2026-03-03", "merchant": "Client Invoice - ACME", "category": "Revenue", "amount": 3200.00},
        ],
        "contacts": [
            {"name": "Jamie Rivera", "company": "ACME Co", "email": "jamie@acme.example", "status": "Active"}
        ],
        "deals": [
            {"deal": "PRISM Retainer", "company": "ACME Co", "stage": "Won", "value": 12000}
        ],
        "tasks": [
            {"task": "Send proposal update", "owner": "Tim", "due": "2026-03-20", "priority": "High", "done": False}
        ],
    }


def ensure_data_file() -> None:
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not DATA_PATH.exists():
        DATA_PATH.write_text(json.dumps(default_data(), indent=2), encoding="utf-8")


def read_data() -> dict[str, list[dict[str, Any]]]:
    ensure_data_file()
    try:
        parsed = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        fallback = default_data()
        write_data(fallback)
        return fallback

    if not isinstance(parsed, dict):
        fallback = default_data()
        write_data(fallback)
        return fallback

    normalized: dict[str, list[dict[str, Any]]] = {
        "transactions": [],
        "contacts": [],
        "deals": [],
        "tasks": [],
    }
    for key in normalized.keys():
        value = parsed.get(key)
        if isinstance(value, list):
            normalized[key] = [row for row in value if isinstance(row, dict)]
    return normalized


def write_data(data: dict[str, list[dict[str, Any]]]) -> None:
    ensure_data_file()
    DATA_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def ensure_quarantine_file() -> None:
    QUARANTINE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not QUARANTINE_PATH.exists():
        QUARANTINE_PATH.write_text("[]", encoding="utf-8")


def read_quarantine() -> list[dict[str, Any]]:
    ensure_quarantine_file()
    try:
        parsed = json.loads(QUARANTINE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        write_quarantine([])
        return []
    if isinstance(parsed, list):
        return [q for q in parsed if isinstance(q, dict)]
    return []


def write_quarantine(quarantine_items: list[dict[str, Any]]) -> None:
    ensure_quarantine_file()
    QUARANTINE_PATH.write_text(json.dumps(quarantine_items, indent=2), encoding="utf-8")


def _get_role_from_token(x_prism_token: str | None) -> str:
    read_token = os.getenv("PRISM_READ_TOKEN")
    admin_token = os.getenv("PRISM_ADMIN_TOKEN")

    # If no tokens configured, allow open access for local prototyping.
    if not read_token and not admin_token:
        return "admin"

    if admin_token and x_prism_token and x_prism_token == admin_token:
        return "admin"
    if read_token and x_prism_token and x_prism_token == read_token:
        return "read"
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")


def require_role(min_role: str, x_prism_token: str | None = Header(default=None)) -> str:
    role = _get_role_from_token(x_prism_token)
    if min_role == "read" and role in {"read", "admin"}:
        return role
    if min_role == "admin" and role == "admin":
        return role
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


def get_read_role(x_prism_token: str | None = Header(default=None)) -> str:
    return require_role("read", x_prism_token=x_prism_token)


def get_admin_role(x_prism_token: str | None = Header(default=None)) -> str:
    return require_role("admin", x_prism_token=x_prism_token)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/data")
def get_data(role: str = Depends(get_read_role)) -> dict[str, list[dict[str, Any]]]:
    return read_data()


@app.put("/data")
def update_data(
    payload: DataPayload,
    role: str = Depends(get_admin_role),
) -> dict[str, str]:
    write_data(payload.model_dump())
    return {"status": "saved"}


@app.get("/quarantine")
def get_quarantine(role: str = Depends(get_read_role)) -> list[dict[str, Any]]:
    return read_quarantine()


class QuarantineAppendPayload(BaseModel):
    items: list[dict[str, Any]]


@app.post("/quarantine/items")
def quarantine_append(
    payload: QuarantineAppendPayload,
    role: str = Depends(get_admin_role),
) -> dict[str, str]:
    quarantine = read_quarantine()
    appended_count = 0
    for item in payload.items:
        if isinstance(item, dict):
            quarantine.append(item)
            appended_count += 1
    write_quarantine(quarantine)
    return {"status": "saved", "count": str(appended_count)}


@app.delete("/quarantine/{item_id}")
def quarantine_delete(
    item_id: str,
    role: str = Depends(get_admin_role),
) -> dict[str, Any]:
    quarantine = read_quarantine()
    new_quarantine = [q for q in quarantine if str(q.get("id")) != item_id]
    write_quarantine(new_quarantine)
    return {"status": "deleted"}


@app.post("/quarantine/{item_id}/restore")
def quarantine_restore(
    item_id: str,
    role: str = Depends(get_admin_role),
) -> dict[str, Any]:
    quarantine = read_quarantine()
    found = next((q for q in quarantine if str(q.get("id")) == item_id), None)
    if not found:
        raise HTTPException(status_code=404, detail="Quarantine item not found")

    section = found.get("section")
    row = found.get("row")
    if not isinstance(section, str) or not isinstance(row, dict):
        raise HTTPException(status_code=400, detail="Malformed quarantine item")

    data = read_data()
    if section not in data or not isinstance(data.get(section), list):
        data[section] = []
    data[section].append(row)

    quarantine = [q for q in quarantine if str(q.get("id")) != item_id]
    write_data(data)
    write_quarantine(quarantine)

    return {"status": "restored"}
