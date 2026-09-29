from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from pathlib import Path

import httpx

from app import logging_config
from app.main import app

REPO_ROOT = Path(__file__).resolve().parents[1]


def run_query(audit_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "audit_query.py"), "--path", str(audit_path), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def send(method: str, url: str, **kwargs) -> httpx.Response:
    async def _send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.request(method, url, **kwargs)

    return asyncio.run(_send())


def test_chat_and_incident_actions_are_audited(monkeypatch, tmp_path: Path, isolated_audit_log: Path) -> None:
    monkeypatch.setattr(logging_config, "LOG_PATH", tmp_path / "logs.jsonl")

    chat = send(
        "POST",
        "/chat",
        headers={"x-request-id": "req-audit001"},
        json={"user_id": "student-01", "session_id": "s-audit", "feature": "qa", "message": "mail a@b.com"},
    )
    enabled = send("POST", "/incidents/rag_slow/enable", headers={"x-operator": "oncall"})
    disabled = send("POST", "/incidents/rag_slow/disable", headers={"x-operator": "oncall"})
    unknown = send("POST", "/incidents/not_real/enable")

    assert (chat.status_code, enabled.status_code, disabled.status_code, unknown.status_code) == (200, 200, 200, 404)
    records = [json.loads(line) for line in isolated_audit_log.read_text(encoding="utf-8").splitlines()]
    assert [(r["action"], r["outcome"]) for r in records] == [
        ("chat.request", "success"),
        ("incident.enable", "success"),
        ("incident.disable", "success"),
        ("incident.enable", "denied"),
    ]
    assert records[0]["correlation_id"] == "req-audit001"
    assert records[0]["actor"].startswith("user:") and "student-01" not in records[0]["actor"]
    assert records[1]["actor"] == "operator:oncall"
    assert records[3]["actor"] == "operator:unknown"
    assert "a@b.com" not in isolated_audit_log.read_text(encoding="utf-8")

    validated = run_query(isolated_audit_log, "--validate")
    assert validated.returncode == 0, validated.stdout
    assert "4/4 bản ghi hợp lệ" in validated.stdout

    by_action = run_query(isolated_audit_log, "--action", "incident.enable", "--outcome", "denied")
    assert [json.loads(line)["resource"] for line in by_action.stdout.splitlines()] == ["incident:not_real"]


def test_validate_rejects_record_outside_schema(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    path.write_text(json.dumps({"action": "chat.delete", "ts": "2026-09-29T00:00:00Z"}) + "\n", encoding="utf-8")

    result = run_query(path, "--validate")

    assert result.returncode == 1
    assert "thiếu field 'actor'" in result.stdout
    assert "không thuộc" in result.stdout


def test_purge_drops_records_older_than_retention(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    old = {"ts": "2026-01-01T00:00:00Z", "action": "chat.request"}
    new = {"ts": "2026-09-20T00:00:00Z", "action": "chat.request"}
    path.write_text("".join(json.dumps(r) + "\n" for r in (old, new)), encoding="utf-8")

    dry = run_query(path, "--purge", "--dry-run", "--now", "2026-09-29T00:00:00Z")
    assert "giữ 1, xóa 1" in dry.stdout
    assert len(path.read_text(encoding="utf-8").splitlines()) == 2

    run_query(path, "--purge", "--now", "2026-09-29T00:00:00Z")
    remaining = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert remaining == [new]
