import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


BASE_DIR = Path(__file__).resolve().parent
CSV_FILE = BASE_DIR / "tf_family_fans_multi.csv"
STATIC_DIR = BASE_DIR / "web"
TIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def parse_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def load_rows(csv_file: Path):
    rows = []
    if not csv_file.exists():
        return rows

    with csv_file.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            timestamp = row.get("time", "").strip()
            tag = row.get("tag", "").strip()
            fans_num = parse_int(row.get("fans_num"))
            collect_num = parse_int(row.get("collect_num"))
            like_num = parse_int(row.get("like_num"))

            if not timestamp or not tag or fans_num is None:
                continue

            try:
                parsed_time = datetime.strptime(timestamp, TIME_FORMAT)
            except ValueError:
                continue

            rows.append(
                {
                    "time": parsed_time,
                    "time_label": parsed_time.strftime(TIME_FORMAT),
                    "tag": tag,
                    "user_id": row.get("user_id", "").strip(),
                    "nick_name": row.get("nick_name", "").strip(),
                    "real_name": row.get("real_name", "").strip(),
                    "fans_num": fans_num,
                    "collect_num": collect_num,
                    "like_num": like_num,
                }
            )

    rows.sort(key=lambda item: (item["tag"], item["time"]))
    return rows


def build_focus_group(ranking, fan_trend_series):
    if not ranking:
        return [], None

    if len(ranking) <= 5:
        focus_window = ranking[:]
    else:
        focus_window = []
        smallest_span = None
        for start in range(0, len(ranking) - 4):
            window = ranking[start:start + 5]
            span = window[0]["fans_num"] - window[-1]["fans_num"]
            if smallest_span is None or span < smallest_span:
                smallest_span = span
                focus_window = window

    if len(ranking) > len(focus_window):
        start_index = next(
            (index for index, item in enumerate(ranking) if item["tag"] == focus_window[0]["tag"]),
            0,
        )
        end_index = start_index + len(focus_window) - 1

        left_gap = None
        if start_index > 0:
            left_gap = ranking[start_index - 1]["fans_num"] - focus_window[0]["fans_num"]

        right_gap = None
        if end_index < len(ranking) - 1:
            right_gap = focus_window[-1]["fans_num"] - ranking[end_index + 1]["fans_num"]

        extension_threshold = 5000
        if right_gap is not None and right_gap <= extension_threshold:
            focus_window = focus_window + [ranking[end_index + 1]]
        elif left_gap is not None and left_gap <= extension_threshold:
            focus_window = [ranking[start_index - 1]] + focus_window

    focus_tags = {item["tag"] for item in focus_window}
    focus_series = [
        series for series in fan_trend_series
        if series["name"] in focus_tags
    ]
    focus_summary = {
        "tags": [item["tag"] for item in focus_window],
        "span": focus_window[0]["fans_num"] - focus_window[-1]["fans_num"],
        "top_fans": focus_window[0]["fans_num"],
        "bottom_fans": focus_window[-1]["fans_num"],
    }
    return focus_series, focus_summary


def summarize_dashboard(rows):
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["tag"]].append(row)

    ranking = []
    fan_trend_series = []
    growth_trend_series = []
    total_fans = 0
    total_growth = 0
    recent_growth_total = 0
    last_updated = None

    for tag, items in grouped.items():
        first = items[0]
        latest = items[-1]
        previous = items[-2] if len(items) > 1 else items[-1]
        total_delta = latest["fans_num"] - first["fans_num"]
        recent_delta = latest["fans_num"] - previous["fans_num"]

        total_fans += latest["fans_num"]
        total_growth += total_delta
        recent_growth_total += recent_delta
        if last_updated is None or latest["time"] > last_updated:
            last_updated = latest["time"]

        ranking.append(
            {
                "tag": tag,
                "user_id": latest["user_id"],
                "fans_num": latest["fans_num"],
                "collect_num": latest["collect_num"],
                "like_num": latest["like_num"],
                "total_growth": total_delta,
                "recent_growth": recent_delta,
                "latest_time": latest["time_label"],
                "nick_name": latest["nick_name"],
                "real_name": latest["real_name"],
            }
        )

        fan_trend_series.append(
            {
                "name": tag,
                "data": [[item["time_label"], item["fans_num"]] for item in items],
            }
        )
        growth_trend_series.append(
            {
                "name": tag,
                "data": [
                    [item["time_label"], item["fans_num"] - first["fans_num"]]
                    for item in items
                ],
            }
        )

    ranking.sort(key=lambda item: item["fans_num"], reverse=True)

    for index, item in enumerate(ranking):
        if index == 0:
            item["gap_to_previous"] = None
        else:
            item["gap_to_previous"] = ranking[index - 1]["fans_num"] - item["fans_num"]

    focus_series, focus_summary = build_focus_group(ranking, fan_trend_series)

    leader = ranking[0] if ranking else None
    fastest_recent = max(ranking, key=lambda item: item["recent_growth"], default=None)
    strongest_total = max(ranking, key=lambda item: item["total_growth"], default=None)
    weakest_recent = min(ranking, key=lambda item: item["recent_growth"], default=None)

    insights = []
    if leader:
        insights.append(
            {
                "title": "当前领跑",
                "content": f'{leader["tag"]} 目前粉丝数最高，达到 {leader["fans_num"]:,}。',
                "tone": "highlight",
            }
        )
    if fastest_recent:
        insights.append(
            {
                "title": "最近冲刺最快",
                "content": (
                    f'{fastest_recent["tag"]} 在最近一次采样中新增 '
                    f'{fastest_recent["recent_growth"]:,} 粉丝。'
                ),
                "tone": "positive",
            }
        )
    if strongest_total:
        insights.append(
            {
                "title": "累计涨幅最佳",
                "content": (
                    f'{strongest_total["tag"]} 自监控开始以来累计增长 '
                    f'{strongest_total["total_growth"]:,} 粉丝。'
                ),
                "tone": "positive",
            }
        )
    if weakest_recent and weakest_recent["recent_growth"] <= 0:
        insights.append(
            {
                "title": "波动提醒",
                "content": (
                    f'{weakest_recent["tag"]} 最近一次采样增长为 '
                    f'{weakest_recent["recent_growth"]:,}，建议关注数据波动或异常。'
                ),
                "tone": "warning",
            }
        )

    return {
        "meta": {
            "member_count": len(ranking),
            "record_count": len(rows),
            "last_updated": last_updated.strftime(TIME_FORMAT) if last_updated else None,
        },
        "summary": {
            "total_fans": total_fans,
            "total_growth": total_growth,
            "recent_growth_total": recent_growth_total,
            "leader_tag": leader["tag"] if leader else None,
        },
        "ranking": ranking,
        "charts": {
            "fans_series": fan_trend_series,
            "growth_series": growth_trend_series,
            "focus_series": focus_series,
        },
        "focus_group": focus_summary,
        "insights": insights,
    }


class DashboardHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, directory=None, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/api/health":
            self.respond_json({"status": "ok"})
            return

        if parsed.path == "/api/dashboard":
            data = summarize_dashboard(load_rows(CSV_FILE))
            self.respond_json(data)
            return

        if parsed.path == "/":
            self.path = "/index.html"

        return super().do_GET()

    def log_message(self, format, *args):
        return

    def respond_json(self, payload, status=HTTPStatus.OK):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def main():
    parser = argparse.ArgumentParser(description="TF family dashboard server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8000, type=int)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), DashboardHandler)
    print(f"Dashboard running at http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
