"""Truy vấn, kiểm tra schema và áp retention cho audit log (data/audit.jsonl).

Ví dụ:
  python scripts/audit_query.py --validate
  python scripts/audit_query.py --action incident.enable
  python scripts/audit_query.py --correlation-id req-1234abcd
  python scripts/audit_query.py --summary
  python scripts/audit_query.py --purge --dry-run
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.cli import configure_utf8_stdio

TYPES = {"string": str, "integer": int, "object": dict, "null": type(None)}


def parse_ts(value: str) -> datetime:
    ts = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return ts if ts.tzinfo else ts.astimezone()


def load_policy(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))["audit"]


def load_records(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def validate_record(record: dict, schema: dict) -> list[str]:
    errors = [f"thiếu field '{name}'" for name in schema["required"] if name not in record]
    props = schema["properties"]
    if schema.get("additionalProperties") is False:
        errors += [f"field lạ '{name}'" for name in record if name not in props]
    for name, rule in props.items():
        if name not in record:
            continue
        value = record[name]
        allowed = rule["type"] if isinstance(rule["type"], list) else [rule["type"]]
        if not any(isinstance(value, TYPES[t]) and not (t == "integer" and isinstance(value, bool)) for t in allowed):
            errors.append(f"'{name}' sai kiểu, cần {allowed}")
            continue
        if "const" in rule and value != rule["const"]:
            errors.append(f"'{name}' phải bằng {rule['const']}")
        if "enum" in rule and value not in rule["enum"]:
            errors.append(f"'{name}'={value!r} không thuộc {rule['enum']}")
        if "pattern" in rule and isinstance(value, str) and not re.search(rule["pattern"], value):
            errors.append(f"'{name}'={value!r} không khớp {rule['pattern']}")
        if rule.get("format") == "date-time":
            try:
                parse_ts(value)
            except ValueError:
                errors.append(f"'{name}' không phải ISO 8601")
    return errors


def matches(record: dict, args: argparse.Namespace) -> bool:
    if args.action and record.get("action") != args.action:
        return False
    if args.actor and record.get("actor") != args.actor:
        return False
    if args.outcome and record.get("outcome") != args.outcome:
        return False
    if args.correlation_id and record.get("correlation_id") != args.correlation_id:
        return False
    ts = parse_ts(record["ts"])
    if args.since and ts < parse_ts(args.since):
        return False
    if args.until and ts > parse_ts(args.until):
        return False
    return True


def main() -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--policy", type=Path, default=REPO_ROOT / "config" / "audit_policy.yaml")
    parser.add_argument("--path", type=Path, help="Mặc định lấy từ policy.")
    parser.add_argument("--action")
    parser.add_argument("--actor")
    parser.add_argument("--outcome")
    parser.add_argument("--correlation-id")
    parser.add_argument("--since", help="ISO 8601")
    parser.add_argument("--until", help="ISO 8601")
    parser.add_argument("--summary", action="store_true", help="Đếm theo action/outcome/actor.")
    parser.add_argument("--validate", action="store_true", help="Kiểm tra mọi bản ghi theo schema.")
    parser.add_argument("--purge", action="store_true", help="Xóa bản ghi quá retention_days.")
    parser.add_argument("--dry-run", action="store_true", help="Dùng với --purge: chỉ in số bản ghi sẽ xóa.")
    parser.add_argument("--now", help="Mốc thời gian để tính retention (ISO 8601); mặc định là bây giờ.")
    args = parser.parse_args()

    policy = load_policy(args.policy)
    path = args.path or REPO_ROOT / policy["path"]
    records = load_records(path)

    if args.validate:
        schema = json.loads((REPO_ROOT / policy["schema"]).read_text(encoding="utf-8"))
        invalid = 0
        for lineno, record in enumerate(records, start=1):
            errors = validate_record(record, schema)
            if errors:
                invalid += 1
                print(f"dòng {lineno}: " + "; ".join(errors))
        print(f"Schema: {len(records) - invalid}/{len(records)} bản ghi hợp lệ ({policy['schema']})")
        return 1 if invalid else 0

    if args.purge:
        now = parse_ts(args.now) if args.now else datetime.now(timezone.utc)
        cutoff = now - timedelta(days=int(policy["retention_days"]))
        keep = [r for r in records if parse_ts(r["ts"]) >= cutoff]
        dropped = len(records) - len(keep)
        print(f"Retention {policy['retention_days']} ngày, cutoff {cutoff.isoformat()}: giữ {len(keep)}, xóa {dropped}")
        if not args.dry_run and dropped:
            path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in keep), encoding="utf-8")
        return 0

    selected = [r for r in records if matches(r, args)]
    if args.summary:
        for key in ("action", "outcome", "actor"):
            counts = Counter(r[key] for r in selected)
            print(f"{key}: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
        print(f"tổng: {len(selected)} bản ghi")
        return 0
    for record in selected:
        print(json.dumps(record, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
