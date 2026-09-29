from __future__ import annotations

from pathlib import Path

import pytest

from app import audit


@pytest.fixture(autouse=True)
def isolated_audit_log(monkeypatch, tmp_path: Path) -> Path:
    """Không để test ghi vào data/audit.jsonl thật."""
    path = tmp_path / "audit.jsonl"
    monkeypatch.setattr(audit, "AUDIT_LOG_PATH", path)
    return path
