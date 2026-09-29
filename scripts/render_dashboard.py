"""Dựng dashboard 6 panel từ data/logs.jsonl theo contract config/dashboard.yaml.

Xuất một file HTML tự chứa (SVG inline, không cần thư viện ngoài) để mở bằng
trình duyệt hoặc chụp làm evidence. Mỗi panel có đơn vị, time range và đường
threshold/SLO lấy đúng từ contract.
"""

from __future__ import annotations

import argparse
import html
import json
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.cli import configure_utf8_stdio
from app.metrics import percentile

UNIT_LABELS = {
    "ms": "ms",
    "requests_per_minute": "req/phút",
    "percent": "%",
    "usd": "USD",
    "tokens": "tokens",
    "score_0_to_1": "điểm 0–1",
}
OPERATORS = {"lte": "≤", "gte": "≥"}
COLORS = ["#2563eb", "#d97706", "#7c3aed", "#0d9488"]
THRESHOLD_COLOR = "#dc2626"


def load_records(path: Path) -> list[dict]:
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
            record["_ts"] = datetime.fromisoformat(record["ts"].replace("Z", "+00:00"))
        except (json.JSONDecodeError, KeyError, ValueError):
            continue
        records.append(record)
    return records


def minute_bins(records: list[dict], end: datetime, minutes: int) -> list[list[dict]]:
    start = end - timedelta(minutes=minutes)
    bins: list[list[dict]] = [[] for _ in range(minutes)]
    for record in records:
        if start <= record["_ts"] < end:
            bins[int((record["_ts"] - start).total_seconds() // 60)].append(record)
    return bins


def of_event(records: list[dict], event: str) -> list[dict]:
    return [r for r in records if r.get("event") == event]


def cumulative(values: list[float]) -> list[float | None]:
    """Cộng dồn; để trống các phút trước request đầu tiên."""
    total, seen, out = 0.0, False, []
    for value in values:
        total += value
        seen = seen or bool(value)
        out.append(total if seen else None)
    return out


def nice_top(value: float) -> float:
    """Làm tròn đỉnh trục Y để 4 khoảng chia là số đẹp."""
    raw = max(value, 1e-9) / 4
    mag = 10 ** math.floor(math.log10(raw))
    step = next(m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw)
    return step * 4


def fmt_tick(value: float, unit: str) -> str:
    if unit == "usd":
        return f"${value:g}"
    if unit == "percent":
        return f"{value:g}%"
    return f"{value:,g}"


def fmt_number(value: float, unit: str) -> str:
    if unit == "usd":
        return f"${value:.4f}" if value < 1 else f"${value:.2f}"
    if unit == "score_0_to_1":
        return f"{value:.2f}"
    if unit == "percent":
        return f"{value:.1f}%"
    if abs(value) >= 1000:
        return f"{value:,.0f}"
    return f"{value:.0f}" if value == int(value) else f"{value:.1f}"


def svg_chart(
    labels: list[str],
    series: list[tuple[str, list[float | None], str]],
    threshold: float,
    threshold_label: str,
    unit: str,
    y_max: float | None = None,
) -> str:
    """series: (tên, giá trị theo phút, kiểu 'line' | 'bar')."""
    width, height = 640, 230
    left, right, top, bottom = 64, 12, 12, 30
    plot_w, plot_h = width - left - right, height - top - bottom
    values = [v for _, vals, _ in series for v in vals if v is not None]
    y_top = y_max if y_max is not None else nice_top(max([threshold, *values]) * 1.1)
    n = len(labels)

    def x(i: float) -> float:
        return left + plot_w * (i + 0.5) / n

    def y(v: float) -> float:
        return top + plot_h * (1 - v / y_top)

    parts = [f'<svg viewBox="0 0 {width} {height}" role="img">']
    for step in range(5):
        v = y_top * step / 4
        parts.append(
            f'<line x1="{left}" x2="{width - right}" y1="{y(v):.1f}" y2="{y(v):.1f}" class="grid"/>'
            f'<text x="{left - 6}" y="{y(v) + 4:.1f}" class="tick" text-anchor="end">'
            f"{html.escape(fmt_tick(v, unit))}</text>"
        )
    for i, label in enumerate(labels):
        if i % 10 == 0 or i == n - 1:
            parts.append(
                f'<text x="{x(i):.1f}" y="{height - 10}" class="tick" text-anchor="middle">{label}</text>'
            )

    bar_series = [s for s in series if s[2] == "bar"]
    bar_w = plot_w / n / max(1, len(bar_series)) * 0.8
    for k, (name, vals, kind) in enumerate(series):
        color = COLORS[k % len(COLORS)]
        if kind == "bar":
            offset = bar_series.index((name, vals, kind)) * bar_w - bar_w * len(bar_series) / 2
            for i, v in enumerate(vals):
                if v:
                    parts.append(
                        f'<rect x="{x(i) + offset:.1f}" y="{y(v):.1f}" width="{bar_w:.1f}" '
                        f'height="{y(0) - y(v):.1f}" fill="{color}" rx="1"/>'
                    )
            continue
        # Series vẽ trước dày hơn để không bị series trùng giá trị (P95 = P99) che mất.
        width_by_order = 1.5 + (len(series) - 1 - k) * 1.2
        segment: list[str] = []
        segments: list[list[str]] = []
        for i, v in enumerate(vals):
            if v is None:
                if segment:
                    segments.append(segment)
                segment = []
                continue
            segment.append(f"{x(i):.1f},{y(v):.1f}")
            parts.append(f'<circle cx="{x(i):.1f}" cy="{y(v):.1f}" r="2.5" fill="{color}"/>')
        if segment:
            segments.append(segment)
        for seg in segments:
            if len(seg) > 1:
                parts.append(
                    f'<polyline points="{" ".join(seg)}" fill="none" stroke="{color}" '
                    f'stroke-width="{width_by_order:.1f}" stroke-linejoin="round"/>'
                )

    ty = y(threshold)
    parts.append(
        f'<line x1="{left}" x2="{width - right}" y1="{ty:.1f}" y2="{ty:.1f}" '
        f'stroke="{THRESHOLD_COLOR}" stroke-width="1.5" stroke-dasharray="6 4"/>'
        f'<text x="{width - right - 4}" y="{ty - 5:.1f}" class="threshold" text-anchor="end">'
        f"{html.escape(threshold_label)}</text>"
    )
    parts.append(
        f'<line x1="{left}" x2="{width - right}" y1="{y(0):.1f}" y2="{y(0):.1f}" class="axis"/></svg>'
    )
    return "".join(parts)


def build_panels(config: dict, bins: list[list[dict]], labels: list[str]) -> list[dict]:
    window = [r for b in bins for r in b]
    sent_all = of_event(window, "response_sent")
    received_all = of_event(window, "request_received")
    failed_all = of_event(window, "request_failed")
    panels = {p["id"]: p for p in config["panels"]}
    out = []

    def add(panel_id: str, stats: list[tuple[str, str]], series, legend_note: str = "", y_max=None):
        panel = panels[panel_id]
        th = panel["threshold"]
        unit = panel["unit"]
        th_label = f"{th['aggregation']} {OPERATORS[th['operator']]} {fmt_number(th['value'], unit)}"
        out.append(
            {
                "title": panel["title"],
                "unit": UNIT_LABELS.get(unit, unit),
                "stats": stats,
                "legend": [(name, COLORS[k % len(COLORS)]) for k, (name, _, _) in enumerate(series)],
                "legend_note": legend_note,
                "threshold_label": th_label,
                "chart": svg_chart(labels, series, th["value"], th_label, unit, y_max),
            }
        )

    def check(value: float, panel_id: str) -> str:
        th = panels[panel_id]["threshold"]
        ok = value <= th["value"] if th["operator"] == "lte" else value >= th["value"]
        return "ok" if ok else "breach"

    # Latency
    lat_all = [r["latency_ms"] for r in sent_all]
    ttft_all = [r["ttft_ms"] for r in sent_all if "ttft_ms" in r]
    series = []
    for p in (50, 95, 99):
        series.append(
            (
                f"P{p}",
                [percentile([r["latency_ms"] for r in of_event(b, "response_sent")], p) or None for b in bins],
                "line",
            )
        )
    series.append(
        ("TTFT P95", [percentile([r.get("ttft_ms", 0) for r in of_event(b, "response_sent")], 95) or None for b in bins], "line")
    )
    p95 = percentile(lat_all, 95)
    add(
        "latency",
        [
            ("P50", f"{percentile(lat_all, 50):.0f} ms"),
            ("P95", f"{p95:.0f} ms|{check(p95, 'latency')}"),
            ("P99", f"{percentile(lat_all, 99):.0f} ms"),
            ("TTFT P95", f"{percentile(ttft_all, 95):.0f} ms"),
        ],
        series,
    )

    # Traffic
    per_min = [len(of_event(b, "request_received")) for b in bins]
    active = [c for c in per_min if c]
    avg_rate = sum(active) / len(active) if active else 0.0
    add(
        "traffic",
        [
            ("Tổng request", f"{len(received_all)}"),
            ("TB req/phút (phút có traffic)", f"{avg_rate:.1f}|{check(avg_rate, 'traffic')}"),
            ("Đỉnh req/phút", f"{max(per_min, default=0)}"),
        ],
        [("request_received / phút", per_min, "bar")],
    )

    # Errors
    rates = []
    for b in bins:
        received = len(of_event(b, "request_received"))
        rates.append(len(of_event(b, "request_failed")) / received * 100 if received else None)
    err_rate = len(failed_all) / len(received_all) * 100 if received_all else 0.0
    tool = [r for r in window if r.get("tool_success") is not None]
    tool_rate = sum(1 for r in tool if r["tool_success"]) / len(tool) * 100 if tool else 0.0
    breakdown: dict[str, int] = {}
    for r in failed_all:
        breakdown[r.get("error_type", "unknown")] = breakdown.get(r.get("error_type", "unknown"), 0) + 1
    breakdown_text = ", ".join(f"{k}: {v}" for k, v in breakdown.items()) or "không có lỗi"
    add(
        "errors",
        [
            ("Error rate", f"{err_rate:.1f}%|{check(err_rate, 'errors')}"),
            ("request_failed", f"{len(failed_all)}"),
            ("Retrieval success", f"{tool_rate:.1f}%"),
        ],
        [("error rate % / phút", rates, "line")],
        legend_note=f"error_type: {breakdown_text}",
        y_max=nice_top(max([3.0, *[r for r in rates if r is not None]]) * 1.1),
    )

    # Cost
    cost_min = [sum(r["cost_usd"] for r in of_event(b, "response_sent")) for b in bins]
    total_cost = sum(cost_min)
    add(
        "cost",
        [
            ("Tổng cost", f"${total_cost:.4f}|{check(total_cost, 'cost')}"),
            ("Cost/request TB", f"${total_cost / len(sent_all):.5f}" if sent_all else "$0"),
        ],
        [("cost tích lũy (USD)", cumulative(cost_min), "line")],
    )

    # Tokens
    tin = [sum(r["tokens_in"] for r in of_event(b, "response_sent")) for b in bins]
    tout = [sum(r["tokens_out"] for r in of_event(b, "response_sent")) for b in bins]
    add(
        "tokens",
        [
            ("tokens_in", f"{sum(tin):,}|{check(sum(tin), 'tokens')}"),
            ("tokens_out", f"{sum(tout):,}|{check(sum(tout), 'tokens')}"),
        ],
        [("tokens_in tích lũy", cumulative(tin), "line"), ("tokens_out tích lũy", cumulative(tout), "line")],
    )

    # Quality
    q_min = []
    for b in bins:
        scores = [r["quality_score"] for r in of_event(b, "response_sent") if "quality_score" in r]
        q_min.append(sum(scores) / len(scores) if scores else None)
    scores_all = [r["quality_score"] for r in sent_all if "quality_score" in r]
    q_mean = sum(scores_all) / len(scores_all) if scores_all else 0.0
    add(
        "quality",
        [("Mean quality_score", f"{q_mean:.2f}|{check(q_mean, 'quality')}"), ("Số response", f"{len(scores_all)}")],
        [("mean / phút", q_min, "line")],
        y_max=1.0,
    )
    return out


def render_html(config: dict, panels: list[dict], start: datetime, end: datetime, source: str) -> str:
    fmt = "%Y-%m-%d %H:%M"
    cards = []
    for p in panels:
        stats = []
        for label, raw in p["stats"]:
            value, _, state = raw.partition("|")
            badge = f'<span class="badge {state}">{"đạt" if state == "ok" else "vượt ngưỡng"}</span>' if state else ""
            stats.append(f'<div class="stat"><span>{html.escape(label)}</span><b>{html.escape(value)}</b>{badge}</div>')
        legend = "".join(
            f'<span><i style="background:{c}"></i>{html.escape(n)}</span>' for n, c in p["legend"]
        )
        legend += f'<span><i class="dash"></i>threshold: {html.escape(p["threshold_label"])}</span>'
        note = f'<div class="note">{html.escape(p["legend_note"])}</div>' if p["legend_note"] else ""
        cards.append(
            f'<section class="card"><header><h2>{html.escape(p["title"])}</h2>'
            f'<span class="unit">đơn vị: {html.escape(p["unit"])}</span></header>'
            f'<div class="stats">{"".join(stats)}</div>{p["chart"]}'
            f'<div class="legend">{legend}</div>{note}</section>'
        )
    dash = config["dashboard"] if "dashboard" in config else config
    return f"""<!doctype html>
<html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="{dash['refresh_seconds']}">
<title>{html.escape(dash['title'])}</title>
<style>
:root {{ --bg:#f6f7f9; --card:#fff; --text:#111827; --muted:#6b7280; --line:#e5e7eb; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--text); font:14px/1.4 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; }}
.top {{ display:flex; flex-wrap:wrap; gap:8px 16px; align-items:baseline; justify-content:space-between; padding:16px 20px 8px; }}
.top h1 {{ font-size:20px; margin:0; }}
.meta {{ display:flex; flex-wrap:wrap; gap:8px; }}
.meta span {{ background:var(--card); border:1px solid var(--line); border-radius:6px; padding:3px 8px; color:var(--muted); }}
.meta b {{ color:var(--text); font-weight:600; }}
.grid2 {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(520px,1fr)); gap:14px; padding:8px 20px 20px; }}
.card {{ background:var(--card); border:1px solid var(--line); border-radius:10px; padding:12px 14px; }}
.card header {{ display:flex; justify-content:space-between; align-items:baseline; gap:8px; }}
.card h2 {{ font-size:15px; margin:0; }}
.unit {{ color:var(--muted); font-size:12px; }}
.stats {{ display:flex; flex-wrap:wrap; gap:6px 18px; margin:8px 0 4px; }}
.stat {{ display:flex; align-items:baseline; gap:6px; }}
.stat span {{ color:var(--muted); font-size:12px; }}
.stat b {{ font-size:17px; font-variant-numeric:tabular-nums; }}
.badge {{ font-size:11px; padding:1px 6px; border-radius:10px; }}
.badge.ok {{ background:#dcfce7; color:#166534; }}
.badge.breach {{ background:#fee2e2; color:#991b1b; }}
svg {{ width:100%; height:auto; display:block; }}
.grid {{ stroke:var(--line); }} .axis {{ stroke:#9ca3af; }}
.tick {{ fill:var(--muted); font-size:11px; }}
.threshold {{ fill:{THRESHOLD_COLOR}; font-size:11px; font-weight:600; paint-order:stroke; stroke:#fff; stroke-width:4px; }}
.legend {{ display:flex; flex-wrap:wrap; gap:4px 14px; font-size:12px; color:var(--muted); }}
.legend i {{ display:inline-block; width:10px; height:10px; border-radius:2px; margin-right:5px; vertical-align:-1px; }}
.legend i.dash {{ height:0; border-top:2px dashed {THRESHOLD_COLOR}; border-radius:0; vertical-align:3px; }}
.note {{ font-size:12px; color:var(--muted); margin-top:4px; }}
@media (max-width:560px) {{ .grid2 {{ grid-template-columns:1fr; padding:8px 16px 16px; }} .top {{ padding:16px 16px 8px; }} }}
</style></head><body>
<div class="top"><h1>{html.escape(dash['title'])}</h1>
<div class="meta"><span>Time range: <b>{dash['time_range_minutes']} phút</b> ({start.strftime(fmt)} → {end.strftime(fmt)})</span>
<span>Bucket: <b>1 phút</b></span><span>Refresh: <b>{dash['refresh_seconds']}s</b></span>
<span>Nguồn: <b>{html.escape(source)}</b></span></div></div>
<main class="grid2">{"".join(cards)}</main></body></html>"""


def main() -> None:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=REPO_ROOT / "config" / "dashboard.yaml")
    parser.add_argument("--logs", type=Path, default=REPO_ROOT / "data" / "logs.jsonl")
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "data" / "dashboard.html")
    parser.add_argument("--end", help="Mốc cuối time range (ISO 8601); mặc định là bây giờ.")
    args = parser.parse_args()

    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))["dashboard"]
    minutes = int(config["time_range_minutes"])
    end = datetime.fromisoformat(args.end) if args.end else datetime.now(timezone.utc)
    if end.tzinfo is None:
        end = end.astimezone()
    end = end.replace(second=0, microsecond=0) + timedelta(minutes=1)
    start = end - timedelta(minutes=minutes)

    bins = minute_bins(load_records(args.logs), end, minutes)
    labels = [(start + timedelta(minutes=i)).astimezone().strftime("%H:%M") for i in range(minutes)]
    panels = build_panels(config, bins, labels)
    args.out.write_text(
        render_html(config, panels, start.astimezone(), end.astimezone(), args.logs.relative_to(REPO_ROOT).as_posix()
                    if args.logs.is_relative_to(REPO_ROOT) else str(args.logs)),
        encoding="utf-8",
    )
    print(f"Đã ghi dashboard: {args.out}")


if __name__ == "__main__":
    main()
