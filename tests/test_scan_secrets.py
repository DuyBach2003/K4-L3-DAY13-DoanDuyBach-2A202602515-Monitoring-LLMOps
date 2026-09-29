from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import scan_secrets  # noqa: E402


def git_repo(tmp_path: Path, files: dict[str, str]) -> Path:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    for rel, content in files.items():
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    subprocess.run(["git", "add", "-f", "."], cwd=tmp_path, check=True)
    return tmp_path


def test_detects_tracked_secret_and_forbidden_file(tmp_path: Path) -> None:
    fake_key = "sk-lf-" + "0123456789abcdef0123"  # ghép chuỗi để chính file test không bị quét trúng
    root = git_repo(tmp_path, {"app/settings.py": f"KEY = '{fake_key}'\n", ".env": "X=1\n"})

    findings = scan_secrets.scan_secrets(root, scan_secrets.tracked_files(root))

    assert any("app/settings.py:1: langfuse_key" in f for f in findings)
    assert ".env: file không được commit" in findings


def test_placeholders_in_env_example_are_not_secrets(tmp_path: Path) -> None:
    root = git_repo(tmp_path, {".env.example": "LANGFUSE_PUBLIC_KEY=pk-lf-...\nLANGFUSE_SECRET_KEY=\n"})

    assert scan_secrets.scan_secrets(root, scan_secrets.tracked_files(root)) == []


def test_detects_raw_pii_in_log_but_not_redacted_values(tmp_path: Path) -> None:
    log = tmp_path / "logs.jsonl"
    log.write_text(
        json.dumps({"payload": {"message_preview": "call 0901234567"}}) + "\n"
        + json.dumps({"payload": {"message_preview": "call [REDACTED_PHONE_VN]"}}) + "\n",
        encoding="utf-8",
    )

    findings = scan_secrets.scan_pii_log(log)

    assert findings == [f"{log}:1: PII thô (phone_vn)"]


def test_repository_is_clean() -> None:
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "scan_secrets.py")],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )

    assert result.returncode == 0, result.stdout
