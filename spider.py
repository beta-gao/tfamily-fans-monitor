import csv
import os
import time
from datetime import datetime
from pathlib import Path

import requests


BASE_URL = "https://app.tfent.cn/member-v2/query/detail"
CSV_FILE = Path(os.environ.get("TF_CSV_FILE", "tf_family_fans_multi.csv"))
POLL_INTERVAL_SECONDS = int(os.environ.get("TF_POLL_INTERVAL_SECONDS", "150"))
AUTH_TOKEN = os.environ.get("TF_AUTH_TOKEN")
USER_AGENT = os.environ.get(
    "TF_USER_AGENT",
    "TFFanclub/5.0.1 (iPhone; iOS 18.5; Scale/3.00)",
)
ACCEPT_LANGUAGE = os.environ.get("TF_ACCEPT_LANGUAGE", "zh-Hans-CA")

TARGETS = [
    {"tag": "", "user_id": 16823136},
    {"tag": "", "user_id": 16823118},
    {"tag": "", "user_id": 16823098},
    {"tag": "", "user_id": 16823128},
    {"tag": "", "user_id": 16823131},
    {"tag": "", "user_id": 16823134},
    {"tag": "", "user_id": 16823140},
    {"tag": "", "user_id": 16823153},
    {"tag": "", "user_id": 18865488},
    {"tag": "", "user_id": 16823123},
]


def build_headers():
    if not AUTH_TOKEN:
        raise RuntimeError(
            "Missing TF_AUTH_TOKEN. Set it in your shell or systemd environment before running spider.py."
        )

    return {
        "User-Agent": USER_AGENT,
        "Authorization": f"Bearer {AUTH_TOKEN}",
        "Accept-Language": ACCEPT_LANGUAGE,
    }


def ensure_csv_exists(csv_path: Path):
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    if not csv_path.exists():
        with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                [
                    "time",
                    "tag",
                    "user_id",
                    "nick_name",
                    "real_name",
                    "fans_num",
                    "collect_num",
                    "like_num",
                ]
            )


def fetch_member_detail(user_id: int, headers):
    response = requests.get(
        BASE_URL,
        headers=headers,
        params={"userId": user_id},
        timeout=20,
    )
    response.raise_for_status()

    data = response.json()
    if data.get("code") != 200:
        raise ValueError(f"API returned non-200 code: {data}")

    member_data = data.get("data", {})
    info_data = member_data.get("info", {})
    return {
        "user_id": member_data.get("userId"),
        "nick_name": member_data.get("nickName"),
        "real_name": member_data.get("realName"),
        "fans_num": info_data.get("fansNum"),
        "collect_num": info_data.get("collectNum"),
        "like_num": info_data.get("likeNum"),
    }


def resolve_tag(tag, detail):
    if tag and tag.strip():
        return tag
    if detail["real_name"]:
        return detail["real_name"]
    if detail["nick_name"]:
        return detail["nick_name"]
    return "UNKNOWN"


def append_row(csv_path: Path, row):
    with csv_path.open("a", newline="", encoding="utf-8-sig") as handle:
        csv.writer(handle).writerow(row)


def poll_once(headers):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for target in TARGETS:
        raw_tag = target["tag"]
        user_id = target["user_id"]

        try:
            detail = fetch_member_detail(user_id, headers)
            tag = resolve_tag(raw_tag, detail)
            row = [
                timestamp,
                tag,
                detail["user_id"],
                detail["nick_name"],
                detail["real_name"],
                detail["fans_num"],
                detail["collect_num"],
                detail["like_num"],
            ]
            append_row(CSV_FILE, row)
            print(f"[{timestamp}] {tag} | fans={detail['fans_num']}")
        except Exception as exc:
            error_row = [
                timestamp,
                raw_tag if raw_tag else "UNKNOWN",
                user_id,
                "",
                "",
                "",
                "",
                f"ERROR: {exc}",
            ]
            append_row(CSV_FILE, error_row)
            print(f"[{timestamp}] {user_id} ERROR: {exc}")


def main():
    headers = build_headers()
    ensure_csv_exists(CSV_FILE)
    print(f"Start polling every {POLL_INTERVAL_SECONDS} seconds")
    print(f"Writing rows to {CSV_FILE}")

    while True:
        poll_once(headers)
        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
