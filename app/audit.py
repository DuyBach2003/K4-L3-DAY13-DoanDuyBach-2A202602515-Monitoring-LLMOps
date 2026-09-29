"""Audit log riêng: ai đã làm gì, lên tài nguyên nào, kết quả ra sao.

Khác với data/logs.jsonl (log vận hành để debug), audit log chỉ ghi hành động có ý
nghĩa kiểm toán, theo schema cố định trong config/audit_schema.json và được giữ
theo retention trong config/audit_policy.yaml.
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .pii import scrub_text

AUDIT_LOG_PATH = Path(os.getenv("AUDIT_LOG_PATH", "data/audit.jsonl"))
SCHEMA_VERSION = 1
_lock = threading.Lock()


def _scrub(value: Any) -> Any:
    if isinstance(value, str):
        return scrub_text(value)
    if isinstance(value, dict):
        return {k: _scrub(v) for k, v in value.items()}
    return value


def write_audit(
    action: str,
    actor: str,
    resource: str,
    outcome: str,
    correlation_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    record = {
        "schema_version": SCHEMA_VERSION,
        "audit_id": uuid.uuid4().hex,
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "action": action,
        "actor": scrub_text(actor),
        "resource": scrub_text(resource),
        "outcome": outcome,
        "correlation_id": correlation_id,
        "details": _scrub(details or {}),
    }
    with _lock:
        AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with AUDIT_LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record
