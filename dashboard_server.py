import argparse
import json
import os
from collections import defaultdict
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from db import TIME_FORMAT, load_dashboard_rows


BASE_DIR = Path(__file__).resolve().parent
DB_FILE = Path(os.environ.get("TF_DB_FILE", str(BASE_DIR / "tf_dashboard.sqlite3")))
STATIC_DIR = Path(os.environ.get("TF_STATIC_DIR", str(BASE_DIR / "web")))
DEFAULT_HOST = os.environ.get("TF_DASHBOARD_HOST", "127.0.0.1")
DEFAULT_PORT = int(os.environ.get("PORT", os.environ.get("TF_DASHBOARD_PORT", "8000")))
EXCLUDED_TAGS = {"瀹樹繆鑷?"}


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
        right_gap = None

        if start_index > 0:
            left_gap = ranking[start_index - 1]["fans_num"] - focus_window[0]["fans_num"]
        if end_index < len(ranking) - 1:
            right_gap = focus_window[-1]["fans_num"] - ranking[end_index + 1]["fans_num"]

        extension_threshold = 5000
        if right_gap is not None and right_gap <= extension_threshold:
            focus_window = focus_window + [ranking[end_index + 1]]
        elif left_gap is not None and left_gap <= extension_threshold:
            focus_window = [ranking[start_index - 1]] + focus_window

    focus_tags = {item["tag"] for item in focus_window}
    focus_series = [series for series in fan_trend_series if series["name"] in focus_tags]
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
    ordered_tags = []
    fan_trend_series = []
    growth_trend_series = []
    total_fans = 0
    total_growth = 0
    recent_growth_total = 0
    last_updated = None
    trend_labels = sorted({row["time_label"] for row in rows})
    update_growth_rows = []

    for tag, items in grouped.items():
        ordered_tags.append(tag)
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

        by_label = {item["time_label"]: item for item in items}
        fan_trend_series.append(
            {
                "name": tag,
                "data": [by_label[label]["fans_num"] if label in by_label else None for label in trend_labels],
            }
        )
        growth_trend_series.append(
            {
                "name": tag,
                "data": [
                    (by_label[label]["fans_num"] - first["fans_num"]) if label in by_label else None
                    for label in trend_labels
                ],
            }
        )

    ordered_tags.sort()
    rows_by_time = defaultdict(dict)
    for row in rows:
        rows_by_time[row["time_label"]][row["tag"]] = row

    previous_snapshot = None
    for time_label in trend_labels:
        snapshot = rows_by_time[time_label]
        deltas = {}
        total_delta_for_row = 0

        for tag in ordered_tags:
            current = snapshot.get(tag)
            if current is None:
                deltas[tag] = None
                continue

            if previous_snapshot and tag in previous_snapshot:
                delta = current["fans_num"] - previous_snapshot[tag]["fans_num"]
            else:
                delta = 0

            deltas[tag] = delta
            total_delta_for_row += delta

        update_growth_rows.append(
            {
                "time": time_label,
                "total_delta": total_delta_for_row,
                "deltas": deltas,
            }
        )
        previous_snapshot = snapshot

    ranking.sort(key=lambda item: item["fans_num"], reverse=True)
    for index, item in enumerate(ranking):
        item["gap_to_previous"] = None if index == 0 else ranking[index - 1]["fans_num"] - item["fans_num"]

    focus_series, focus_summary = build_focus_group(ranking, fan_trend_series)
    leader = ranking[0] if ranking else None
    fastest_recent = max(ranking, key=lambda item: item["recent_growth"], default=None)
    strongest_total = max(ranking, key=lambda item: item["total_growth"], default=None)
    weakest_recent = min(ranking, key=lambda item: item["recent_growth"], default=None)

    insights = []
    if leader:
        insights.append(
            {
                "title": "褰撳墠棰嗚窇",
                "content": f'{leader["tag"]} 鐩墠绮変笣鏁版渶楂橈紝杈惧埌 {leader["fans_num"]:,}銆?',
                "tone": "highlight",
            }
        )
    if fastest_recent:
        insights.append(
            {
                "title": "鏈€杩戝啿鍒烘渶蹇?",
                "content": f'{fastest_recent["tag"]} 鍦ㄦ渶杩戜竴娆￠噰鏍蜂腑鏂板 {fastest_recent["recent_growth"]:,} 绮変笣銆?',
                "tone": "positive",
            }
        )
    if strongest_total:
        insights.append(
            {
                "title": "绱娑ㄥ箙鏈€浣?",
                "content": f'{strongest_total["tag"]} 鑷洃鎺у紑濮嬩互鏉ョ疮璁″闀?{strongest_total["total_growth"]:,} 绮変笣銆?',
                "tone": "positive",
            }
        )
    if weakest_recent and weakest_recent["recent_growth"] <= 0:
        insights.append(
            {
                "title": "娉㈠姩鎻愰啋",
                "content": f'{weakest_recent["tag"]} 鏈€杩戜竴娆￠噰鏍峰闀夸负 {weakest_recent["recent_growth"]:,}锛屽缓璁叧娉ㄦ暟鎹尝鍔ㄦ垨寮傚父銆?',
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
            "trend_labels": trend_labels,
            "fans_series": fan_trend_series,
            "growth_series": growth_trend_series,
            "focus_series": focus_series,
        },
        "update_growth": {
            "tags": ordered_tags,
            "rows": update_growth_rows,
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
            self.respond_json(summarize_dashboard(load_dashboard_rows(DB_FILE, EXCLUDED_TAGS)))
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
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", default=DEFAULT_PORT, type=int)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), DashboardHandler)
    print(f"Dashboard running at http://{args.host}:{args.port}")
    print(f"Reading SQLite from {DB_FILE}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
