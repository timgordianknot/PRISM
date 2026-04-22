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


def test_quarantine_restore_moves_row_into_data_and_removes_item(tmp_path, monkeypatch):
    data_file = tmp_path / "fincrm_data.json"
    quarantine_file = tmp_path / "fincrm_quarantine.json"
    data_file.write_text(json.dumps(main.default_data(), indent=2), encoding="utf-8")
    quarantine_item = {
        "id": "q-1",
        "section": "tasks",
        "row": {
            "task": "Recovered task",
            "owner": "QA",
            "due": "2026-04-01",
            "priority": "Medium",
            "done": False,
        },
    }
    quarantine_file.write_text(json.dumps([quarantine_item], indent=2), encoding="utf-8")

    monkeypatch.setattr(main, "DATA_PATH", data_file)
    monkeypatch.setattr(main, "QUARANTINE_PATH", quarantine_file)
    _set_env(monkeypatch, read_token=None, admin_token=None)

    client = TestClient(main.app)
    restore = client.post("/quarantine/q-1/restore")
    assert restore.status_code == 200
    assert restore.json()["status"] == "restored"

    updated_data = json.loads(data_file.read_text(encoding="utf-8"))
    assert any(row.get("task") == "Recovered task" for row in updated_data["tasks"])

    updated_quarantine = json.loads(quarantine_file.read_text(encoding="utf-8"))
    assert updated_quarantine == []


def test_quarantine_delete_removes_item_by_id(tmp_path, monkeypatch):
    quarantine_file = tmp_path / "fincrm_quarantine.json"
    items = [
        {"id": "q-keep", "section": "tasks", "row": {"task": "Keep me"}},
        {"id": "q-drop", "section": "tasks", "row": {"task": "Drop me"}},
    ]
    quarantine_file.write_text(json.dumps(items, indent=2), encoding="utf-8")
    monkeypatch.setattr(main, "QUARANTINE_PATH", quarantine_file)
    _set_env(monkeypatch, read_token=None, admin_token=None)

    client = TestClient(main.app)
    response = client.delete("/quarantine/q-drop")
    assert response.status_code == 200
    assert response.json()["status"] == "deleted"

    updated = json.loads(quarantine_file.read_text(encoding="utf-8"))
    assert len(updated) == 1
    assert updated[0]["id"] == "q-keep"


def test_write_data_is_atomic_and_leaves_no_tmp(tmp_path, monkeypatch):
    data_file = tmp_path / "fincrm_data.json"
    monkeypatch.setattr(main, "DATA_PATH", data_file)

    payload = {"transactions": [], "contacts": [], "deals": [], "tasks": []}
    main.write_data(payload)

    assert data_file.exists()
    parsed = json.loads(data_file.read_text(encoding="utf-8"))
    assert parsed == payload
    assert not (tmp_path / "fincrm_data.json.tmp").exists()


def test_write_quarantine_is_atomic_and_leaves_no_tmp(tmp_path, monkeypatch):
    quarantine_file = tmp_path / "fincrm_quarantine.json"
    monkeypatch.setattr(main, "QUARANTINE_PATH", quarantine_file)

    payload = [{"id": "q-1", "section": "tasks", "row": {"task": "x"}}]
    main.write_quarantine(payload)

    assert quarantine_file.exists()
    parsed = json.loads(quarantine_file.read_text(encoding="utf-8"))
    assert parsed == payload
    assert not (tmp_path / "fincrm_quarantine.json.tmp").exists()
