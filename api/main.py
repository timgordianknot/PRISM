from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel
from prism_schema import SECTION_KEYS, normalize_data, validate_dataset, validate_row
from prism_storage import (
    file_locks,
    load_json_unlocked,
    mutate_json_file,
    read_json_file,
    save_json_unlocked,
    write_json_file,
)

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
    read_json_file(DATA_PATH, default_factory=default_data)


def read_data() -> dict[str, list[dict[str, Any]]]:
    payload = read_json_file(DATA_PATH, default_factory=default_data)
    return normalize_data(payload)


def write_data(data: dict[str, list[dict[str, Any]]]) -> None:
    write_json_file(DATA_PATH, data)


def ensure_quarantine_file() -> None:
    read_json_file(QUARANTINE_PATH, default_factory=list)


def read_quarantine() -> list[dict[str, Any]]:
    parsed = read_json_file(QUARANTINE_PATH, default_factory=list)
    if isinstance(parsed, list):
        return [q for q in parsed if isinstance(q, dict)]
    return []


def write_quarantine(quarantine_items: list[dict[str, Any]]) -> None:
    write_json_file(QUARANTINE_PATH, quarantine_items)


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
    validated_data, issues = validate_dataset(payload.model_dump())
    if issues:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "Payload failed schema validation",
                "issues": issues,
            },
        )
    write_data(validated_data)
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
    appended_count = 0

    def mutate(quarantine: Any) -> list[dict[str, Any]]:
        nonlocal appended_count
        existing = [q for q in quarantine if isinstance(q, dict)] if isinstance(quarantine, list) else []
        for item in payload.items:
            if isinstance(item, dict):
                existing.append(item)
                appended_count += 1
        return existing

    mutate_json_file(QUARANTINE_PATH, default_factory=list, mutator=mutate)
    return {"status": "saved", "count": str(appended_count)}


@app.delete("/quarantine/{item_id}")
def quarantine_delete(
    item_id: str,
    role: str = Depends(get_admin_role),
) -> dict[str, Any]:
    def mutate(quarantine: Any) -> list[dict[str, Any]]:
        existing = [q for q in quarantine if isinstance(q, dict)] if isinstance(quarantine, list) else []
        return [q for q in existing if str(q.get("id")) != item_id]

    mutate_json_file(QUARANTINE_PATH, default_factory=list, mutator=mutate)
    return {"status": "deleted"}


@app.post("/quarantine/{item_id}/restore")
def quarantine_restore(
    item_id: str,
    role: str = Depends(get_admin_role),
) -> dict[str, Any]:
    with file_locks([DATA_PATH, QUARANTINE_PATH]):
        quarantine_raw = load_json_unlocked(QUARANTINE_PATH, default_factory=list, initialize_if_missing=True)
        quarantine = [q for q in quarantine_raw if isinstance(q, dict)] if isinstance(quarantine_raw, list) else []
        found = next((q for q in quarantine if str(q.get("id")) == item_id), None)
        if not found:
            raise HTTPException(status_code=404, detail="Quarantine item not found")

        section = found.get("section")
        row = found.get("row")
        if not isinstance(section, str) or not isinstance(row, dict):
            raise HTTPException(status_code=400, detail="Malformed quarantine item")
        if section not in SECTION_KEYS:
            raise HTTPException(status_code=400, detail=f"Unknown section '{section}'")

        normalized_row, reasons = validate_row(section, row)
        if reasons:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "Quarantine row still fails validation",
                    "reasons": reasons,
                },
            )
        assert normalized_row is not None

        data_raw = load_json_unlocked(DATA_PATH, default_factory=default_data, initialize_if_missing=True)
        data = normalize_data(data_raw)
        if section not in data or not isinstance(data.get(section), list):
            data[section] = []
        data[section].append(normalized_row)

        remaining_quarantine = [q for q in quarantine if str(q.get("id")) != item_id]
        save_json_unlocked(DATA_PATH, data)
        save_json_unlocked(QUARANTINE_PATH, remaining_quarantine)

    return {"status": "restored"}
