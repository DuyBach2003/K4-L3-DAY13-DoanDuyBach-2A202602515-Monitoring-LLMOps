"""Quét repo trước khi push: secret trong file đã track, file cấm commit, PII thô.

- Mọi file text do git track: tìm key Langfuse/Anthropic/OpenAI/AWS, private key.
- Các file tuyệt đối không được track: .env, config/challenge.json, log runtime, .venv.
- submission/REPORT.md và các file log truyền qua --logs: tìm PII thô bằng đúng
  pattern của app/pii.py (email, SĐT Việt Nam, CCCD, thẻ, passport).

Thoát với mã 1 nếu có phát hiện, để dùng làm gate trong CI.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.cli import configure_utf8_stdio
from app.pii import PII_PATTERNS

SECRET_PATTERNS = {
    "langfuse_key": r"\b(?:sk|pk)-lf-[A-Za-z0-9-]{16,}",
    "anthropic_key": r"\bsk-ant-[A-Za-z0-9_-]{20,}",
    "openai_key": r"\bsk-(?:proj-)?[A-Za-z0-9]{32,}",
    "aws_access_key": r"\bAKIA[0-9A-Z]{16}\b",
    "private_key": r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
}
FORBIDDEN_PATHS = (".env", "config/challenge.json", "data/logs.jsonl", "data/audit.jsonl")
FORBIDDEN_PREFIXES = (".venv/", "__pycache__/")
PII_TEXT_FILES = ("submission/REPORT.md",)


def tracked_files(root: Path) -> list[str]:
    out = subprocess.run(["git", "ls-files"], cwd=root, capture_output=True, text=True, check=True)
    return [line for line in out.stdout.splitlines() if line]


def read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None  # file nhị phân như ảnh evidence


def scan_secrets(root: Path, files: list[str]) -> list[str]:
    findings = []
    for rel in files:
        if rel in FORBIDDEN_PATHS or rel.startswith(FORBIDDEN_PREFIXES) or "/__pycache__/" in rel:
            findings.append(f"{rel}: file không được commit")
            continue
        text = read_text(root / rel)
        if text is None:
            continue
        for name, pattern in SECRET_PATTERNS.items():
            for match in re.finditer(pattern, text):
                line = text.count("\n", 0, match.start()) + 1
                findings.append(f"{rel}:{line}: {name} ({match.group()[:10]}...)")
    return findings


def pii_hits(text: str) -> list[str]:
    return [name for name, pattern in PII_PATTERNS.items() if re.search(pattern, text)]


def string_values(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from string_values(item)
    elif isinstance(value, list):
        for item in value:
            yield from string_values(item)


def scan_pii_text(root: Path, rel: str) -> list[str]:
    text = read_text(root / rel)
    if text is None:
        return []
    findings = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for name in pii_hits(line):
            findings.append(f"{rel}:{lineno}: PII thô ({name})")
    return findings


def scan_pii_log(path: Path) -> list[str]:
    findings = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            findings.append(f"{path}:{lineno}: không phải JSON")
            continue
        for value in string_values(record):
            for name in pii_hits(value):
                findings.append(f"{path}:{lineno}: PII thô ({name})")
    return findings


def main() -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument("--logs", type=Path, nargs="*", default=[], help="File JSONL cần quét PII thô.")
    args = parser.parse_args()

    files = tracked_files(args.root)
    findings = scan_secrets(args.root, files)
    for rel in PII_TEXT_FILES:
        if rel in files:
            findings += scan_pii_text(args.root, rel)
    for log_path in args.logs:
        if log_path.exists():
            findings += scan_pii_log(log_path)

    for finding in findings:
        print(finding)
    scanned_logs = [str(p) for p in args.logs if p.exists()]
    print(
        f"Đã quét {len(files)} file track, {len(PII_TEXT_FILES)} file report, "
        f"{len(scanned_logs)} file log ({', '.join(scanned_logs) or 'không có'}): "
        f"{len(findings)} phát hiện"
    )
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
