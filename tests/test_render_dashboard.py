from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def record(ts: str, event: str, **fields) -> str:
    return json.dumps({"ts": ts, "event": event, **fields}) + "\n"


def test_render_marks_latency_breach_against_contract_threshold(tmp_path: Path) -> None:
    logs = tmp_path / "logs.jsonl"
    lines = []
    for i, latency in enumerate([160, 2660, 2665]):
        ts = f"2026-09-29T09:05:{10 + i:02d}Z"
        lines.append(record(ts, "request_received"))
        lines.append(record(ts, "response_sent", latency_ms=latency, ttft_ms=55, tokens_in=40,
                            tokens_out=100, cost_usd=0.002, quality_score=0.9, tool_success=True))
    logs.write_text("".join(lines), encoding="utf-8")
    out = tmp_path / "dashboard.html"

    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "render_dashboard.py"),
         "--logs", str(logs), "--out", str(out), "--end", "2026-09-29T09:06:00+00:00"],
        cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8", check=False,
    )

    assert result.returncode == 0, result.stderr
    page = out.read_text(encoding="utf-8")
    for title in ("Latency percentiles and TTFT", "Request traffic", "Error rate and retrieval success",
                  "Cost over time", "Input and output tokens", "Quality proxy"):
        assert title in page
    assert "p95 ≤ 2,000" in page
    assert '<b>2665 ms</b><span class="badge breach">' in page
