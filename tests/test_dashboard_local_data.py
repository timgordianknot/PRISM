from __future__ import annotations

import json
from pathlib import Path

import apps.fincrm_dashboard as dashboard


def test_load_local_data_recovers_from_invalid_json(tmp_path: Path, monkeypatch) -> None:
    data_file = tmp_path / "fincrm_data.json"
    data_file.write_text("{not-valid-json", encoding="utf-8")

    monkeypatch.setattr(dashboard, "DATA_PATH", data_file)

    loaded = dashboard.load_local_data()

    assert isinstance(loaded, dict)
    assert set(loaded.keys()) == {"transactions", "contacts", "deals", "tasks"}

    corrupt_backup = tmp_path / "fincrm_data.corrupt.json"
    assert corrupt_backup.exists()
    assert "{not-valid-json" in corrupt_backup.read_text(encoding="utf-8")

    healed = json.loads(data_file.read_text(encoding="utf-8"))
    assert isinstance(healed, dict)
    assert set(healed.keys()) == {"transactions", "contacts", "deals", "tasks"}


def test_save_local_data_writes_atomic_and_no_tmp_left(tmp_path: Path, monkeypatch) -> None:
    data_file = tmp_path / "fincrm_data.json"
    monkeypatch.setattr(dashboard, "DATA_PATH", data_file)

    payload = {
        "transactions": [],
        "contacts": [],
        "deals": [],
        "tasks": [],
    }
    dashboard.save_local_data(payload)

    assert data_file.exists()
    parsed = json.loads(data_file.read_text(encoding="utf-8"))
    assert parsed == payload
    assert not (tmp_path / "fincrm_data.json.tmp").exists()
