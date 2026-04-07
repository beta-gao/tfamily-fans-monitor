import argparse
import json
import os
from collections import defaultdict
from datetime import timedelta
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from db import TIME_FORMAT, load_dashboard_rows
from targets import ACTIVE_USER_IDS


BASE_DIR = Path(__file__).resolve().parent
DB_FILE = Path(os.environ.get("TF_DB_FILE", str(BASE_DIR / "tf_dashboard.sqlite3")))
STATIC_DIR = Path(os.environ.get("TF_STATIC_DIR", str(BASE_DIR / "web")))
DEFAULT_HOST = os.environ.get("TF_DASHBOARD_HOST", "127.0.0.1")
DEFAULT_PORT = int(os.environ.get("PORT", os.environ.get("TF_DASHBOARD_PORT", "8000")))
EXCLUDED_TAGS = {"官方账号"}
DEFAULT_RANGE_KEY = "7d"
RANGE_DELTAS = {
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
    "all": None,
}
RANK_CHANGE_WINDOW = timedelta(hours=1)


def group_rows(rows):
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["tag"]].append(row)
    return grouped


def latest_row_at_or_before(items, cutoff):
    for item in reversed(items):
        if item["time"] <= cutoff:
            return item
    return None


def row_n_samples_back(items, samples):
    index = len(items) - 1 - samples
    if index < 0:
        return None
    return items[index]


def filter_rows_for_range(grouped, last_updated, range_key):
    delta = RANGE_DELTAS.get(range_key, RANGE_DELTAS[DEFAULT_RANGE_KEY])
    if delta is None or last_updated is None:
        return [row for items in grouped.values() for row in items]

    cutoff = last_updated - delta
    filtered = []
    for items in grouped.values():
        baseline = latest_row_at_or_before(items, cutoff)
        if baseline is not None:
            filtered.append(baseline)
        filtered.extend(item for item in items if item["time"] > cutoff)
    return filtered


def build_rank_change_map(grouped, last_updated):
    if last_updated is None:
        return {}

    comparison_time = last_updated - RANK_CHANGE_WINDOW
    previous_rows = []
    for tag, items in grouped.items():
        previous = latest_row_at_or_before(items, comparison_time)
        if previous is None:
            continue
        previous_rows.append({"tag": tag, "fans_num": previous["fans_num"]})

    previous_rows.sort(key=lambda item: item["fans_num"], reverse=True)
    return {item["tag"]: index + 1 for index, item in enumerate(previous_rows)}


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


def summarize_dashboard(rows, range_key):
    grouped = group_rows(rows)
    ranking = []
    total_fans = 0
    total_growth = 0
    recent_growth_total = 0
    last_updated = None

    for items in grouped.values():
        latest = items[-1]
        if last_updated is None or latest["time"] > last_updated:
            last_updated = latest["time"]

    previous_ranks = build_rank_change_map(grouped, last_updated)

    for tag, items in grouped.items():
        first = items[0]
        latest = items[-1]
        previous = items[-2] if len(items) > 1 else None
        total_delta = latest["fans_num"] - first["fans_num"]
        latest_delta = latest["fans_num"] - previous["fans_num"] if previous else None
        baseline_24_samples = row_n_samples_back(items, 24)
        baseline_24h = latest_row_at_or_before(items, latest["time"] - timedelta(hours=24))

        total_fans += latest["fans_num"]
        total_growth += total_delta
        recent_growth_total += latest_delta or 0

        ranking.append(
            {
                "tag": tag,
                "user_id": latest["user_id"],
                "fans_num": latest["fans_num"],
                "collect_num": latest["collect_num"],
                "like_num": latest["like_num"],
                "total_growth": total_delta,
                "latest_growth": latest_delta,
                "growth_24_samples": None
                if baseline_24_samples is None
                else latest["fans_num"] - baseline_24_samples["fans_num"],
                "growth_24h": None if baseline_24h is None else latest["fans_num"] - baseline_24h["fans_num"],
                "latest_time": latest["time_label"],
                "nick_name": latest["nick_name"],
                "real_name": latest["real_name"],
            }
        )

    ranking.sort(key=lambda item: item["fans_num"], reverse=True)
    for index, item in enumerate(ranking):
        item["rank"] = index + 1
        item["gap_to_previous"] = None if index == 0 else ranking[index - 1]["fans_num"] - item["fans_num"]
        previous_rank = previous_ranks.get(item["tag"])
        item["rank_change"] = None if previous_rank is None else previous_rank - item["rank"]

    chart_rows = filter_rows_for_range(grouped, last_updated, range_key)
    chart_grouped = group_rows(chart_rows)
    trend_labels = sorted({row["time_label"] for row in chart_rows})

    fan_trend_series = []
    growth_trend_series = []
    update_growth_rows = []
    ordered_tags = [item["tag"] for item in ranking]

    for tag in ordered_tags:
        items = chart_grouped.get(tag, [])
        if not items:
            continue

        first = items[0]
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

    rows_by_time = defaultdict(dict)
    for row in chart_rows:
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

    focus_series, focus_summary = build_focus_group(ranking, fan_trend_series)
    leader = ranking[0] if ranking else None
    fastest_recent = max(
        (item for item in ranking if item["latest_growth"] is not None),
        key=lambda item: item["latest_growth"],
        default=None,
    )
    strongest_24h = max(
        (item for item in ranking if item["growth_24h"] is not None),
        key=lambda item: item["growth_24h"],
        default=None,
    )

    insights = []
    if leader:
        insights.append(
            {
                "title": "Current Leader",
                "content": f'{leader["tag"]} currently leads with {leader["fans_num"]:,} fans.',
                "tone": "highlight",
            }
        )
    if fastest_recent:
        insights.append(
            {
                "title": "Fastest Latest Update",
                "content": f'{fastest_recent["tag"]} gained {fastest_recent["latest_growth"]:,} fans in the latest sample.',
                "tone": "positive",
            }
        )
    if strongest_24h:
        insights.append(
            {
                "title": "Strongest 24h Growth",
                "content": f'{strongest_24h["tag"]} is up {strongest_24h["growth_24h"]:,} fans over the last 24 hours.',
                "tone": "positive",
            }
        )
    movers = [item for item in ranking if item["rank_change"]]
    if movers:
        biggest_mover = max(movers, key=lambda item: abs(item["rank_change"]))
        direction = "up" if biggest_mover["rank_change"] > 0 else "down"
        insights.append(
            {
                "title": "Ranking Mover",
                "content": f'{biggest_mover["tag"]} moved {direction} {abs(biggest_mover["rank_change"])} place(s) versus one hour ago.',
                "tone": "warning" if direction == "down" else "positive",
            }
        )

    return {
        "meta": {
            "member_count": len(ranking),
            "record_count": len(rows),
            "last_updated": last_updated.strftime(TIME_FORMAT) if last_updated else None,
            "range": range_key,
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
            params = parse_qs(parsed.query)
            range_key = params.get("range", [DEFAULT_RANGE_KEY])[0]
            if range_key not in RANGE_DELTAS:
                range_key = DEFAULT_RANGE_KEY
            rows = load_dashboard_rows(DB_FILE, EXCLUDED_TAGS, ACTIVE_USER_IDS)
            self.respond_json(summarize_dashboard(rows, range_key))
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
