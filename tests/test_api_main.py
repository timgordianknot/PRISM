from __future__ import annotations

import json

from fastapi.testclient import TestClient

from api import main


def _set_env(monkeypatch, read_token: str | None, admin_token: str | None) -> None:
    if read_token is None:
        monkeypatch.delenv("PRISM_READ_TOKEN", raising=False)
    else:
        monkeypatch.setenv("PRISM_READ_TOKEN", read_token)
    if admin_token is None:
        monkeypatch.delenv("PRISM_ADMIN_TOKEN", raising=False)
    else:
        monkeypatch.setenv("PRISM_ADMIN_TOKEN", admin_token)


def test_read_data_recovers_from_invalid_json(tmp_path, monkeypatch):
    data_file = tmp_path / "fincrm_data.json"
    data_file.write_text("{invalid", encoding="utf-8")
    monkeypatch.setattr(main, "DATA_PATH", data_file)

    payload = main.read_data()
    assert isinstance(payload, dict)
    assert set(payload.keys()) == {"transactions", "contacts", "deals", "tasks"}
    persisted = json.loads(data_file.read_text(encoding="utf-8"))
    assert isinstance(persisted, dict)
    assert set(persisted.keys()) == {"transactions", "contacts", "deals", "tasks"}


def test_quarantine_append_returns_actual_appended_count(tmp_path, monkeypatch):
    quarantine_file = tmp_path / "fincrm_quarantine.json"
    quarantine_file.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(main, "QUARANTINE_PATH", quarantine_file)
    _set_env(monkeypatch, read_token=None, admin_token=None)

    client = TestClient(main.app)
    response = client.post("/quarantine/items", json={"items": [{"id": "a"}, "not-a-dict", {"id": "b"}]})
    assert response.status_code == 200
    assert response.json()["count"] == "2"


def test_auth_matrix_read_vs_admin(monkeypatch):
    _set_env(monkeypatch, read_token="read-123", admin_token="admin-456")
    client = TestClient(main.app)

    # No token -> unauthorized
    assert client.get("/data").status_code == 401

    # Read token can read
    assert client.get("/data", headers={"X-PRISM-TOKEN": "read-123"}).status_code == 200

    # Read token cannot write
    payload = {"transactions": [], "contacts": [], "deals": [], "tasks": []}
    assert client.put("/data", json=payload, headers={"X-PRISM-TOKEN": "read-123"}).status_code == 403

    # Admin token can write
    assert client.put("/data", json=payload, headers={"X-PRISM-TOKEN": "admin-456"}).status_code == 200
