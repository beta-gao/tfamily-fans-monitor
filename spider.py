import requests
import csv
import time
from datetime import datetime
from pathlib import Path

BASE_URL = "https://app.tfent.cn/member-v2/query/detail"
POLL_INTERVAL_SECONDS = 150
CSV_FILE = "tf_family_fans_multi.csv"

HEADERS = {
    "User-Agent": "TFFanclub/5.0.1 (iPhone; iOS 18.5; Scale/3.00)",
    "Authorization": "Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJjdXJyZW50VXNlciI6eyJ1c2VySWQiOjIyMTU5NTM2LCJzeXNDb2RlIjoidGYiLCJhY2NvdW50IjoiOUE4QkQyMjI0ODE4NDcxQkE0QzFGMDEzODI1NTREQjciLCJhY2NvdW50VHlwZSI6MiwiY29tcGFueUlkIjoyLCJpbnRlcmlvcklkIjpudWxsLCJtYWluT3JnSWQiOm51bGwsInBsYXRmb3JtIjoxLCJvcmdJZCI6bnVsbCwib3JnSWRzIjpudWxsLCJkZXZpY2VDb2RlIjpudWxsLCJvcGVuSWQiOiJvZnhOejZ1U095OEhPa3g2ZWZHSGdxM1c4dFRBIiwiYXBwbGV0T3BlbklkIjoibzcxWjU1VGxreHRWdGVQV2FGOU5hbVFoQlhmWSIsInBob25lIjoiMTUxNjcxNjg3MTEiLCJlbWFpbCI6bnVsbCwibmlja05hbWUiOiIiLCJjb21wYW55TmFtZSI6IlRGIiwib3JnTmFtZSI6bnVsbCwidXNlcktpbmQiOjIsInBsYXRmb3JtQ29tcGFueUlkIjoyLCJwbGF0Zm9ybU9yZ0lkIjozNSwicGxhdGZvcm1Db21wYW55TmFtZSI6IlRGIiwicGxhdGZvcm1PcmdOYW1lIjoiVEYiLCJyb2xlVHlwZSI6bnVsbCwiY2hhbm5lbCI6MywibG9naW5QbGF0Zm9ybSI6LTF9LCJjb2RlIjoyMDAsInVzZXJfbmFtZSI6IjlBOEJEMjIyNDgxODQ3MUJBNEMxRjAxMzgyNTU0REI3Iiwic2NvcGUiOlsiYXBwIl0sImV4cCI6MTc3Njc4ODg1MSwiZXhwaXJhdGlvbl9kYXRlIjoxNzc2Nzg4ODUxNDkwLCJqdGkiOiIyZDFjNDIxOC1hNzgxLTQ1ODYtOGU4YS1kZDgwOGM4YzYzZmMiLCJjbGllbnRfaWQiOiJ0ZiJ9.aQP736IN0hHxSbfuhLTg8G75_YlOq9NE05Xi2wA2GEFub2zCbvZyH7zjzuVpkmvx2EzZ8kKxtrmRCTu0gS2UlP64NC-6SkkzburLVUzSLJM8eKXE0JGIxVVt1__1cfb1rpuyvrzjr4HqYRMFnEF2HYlOZRkJxt6H_MpvnTPJSLLWe5Wat-Mdyg5J_eHechZBGdKfFp_ngVjojCc8k493bzhshGzoMJXbKHZgP6soNlOjwXAdSQcF2-n15YQOUrrv9Qy-UQVyAf8kr2o_C8ogo6au-DMPMOjfYHxwnLOszYl9b0xp3liPddlUzLrgX0VBVIys44OMpDqWpuVXQDQhMw",
    "Accept-Language": "zh-Hans-CA"
}

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
    {"tag": "", "user_id": 16823123}
]

def ensure_csv_exists(csv_path):
    path = Path(csv_path)
    if not path.exists():
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow([
                "time",
                "tag",
                "user_id",
                "nick_name",
                "real_name",
                "fans_num",
                "collect_num",
                "like_num"
            ])

def fetch_member_detail(user_id):
    params = {"userId": user_id}
    response = requests.get(
        BASE_URL,
        headers=HEADERS,
        params=params,
        timeout=20
    )
    response.raise_for_status()

    data = response.json()

    if data.get("code") != 200:
        raise ValueError("API returned non-200 code: " + str(data))

    member_data = data.get("data", {})
    info_data = member_data.get("info", {})

    result = {
        "user_id": member_data.get("userId"),
        "nick_name": member_data.get("nickName"),
        "real_name": member_data.get("realName"),
        "fans_num": info_data.get("fansNum"),
        "collect_num": info_data.get("collectNum"),
        "like_num": info_data.get("likeNum")
    }
    return result

def resolve_tag(tag, detail):
    # 如果用户手动填了tag，就优先用
    if tag and tag.strip():
        return tag

    # 自动 fallback 逻辑
    if detail["real_name"]:
        return detail["real_name"]
    elif detail["nick_name"]:
        return detail["nick_name"]
    else:
        return "UNKNOWN"

def append_row(csv_path, row):
    with open(csv_path, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(row)

def poll_once():
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for target in TARGETS:
        raw_tag = target["tag"]
        user_id = target["user_id"]

        try:
            detail = fetch_member_detail(user_id)

            tag = resolve_tag(raw_tag, detail)

            row = [
                timestamp,
                tag,
                detail["user_id"],
                detail["nick_name"],
                detail["real_name"],
                detail["fans_num"],
                detail["collect_num"],
                detail["like_num"]
            ]
            append_row(CSV_FILE, row)

            print(
                "[" + timestamp + "] "
                + tag
                + " | fans="
                + str(detail["fans_num"])
            )

        except Exception as e:
            error_row = [
                timestamp,
                raw_tag if raw_tag else "UNKNOWN",
                user_id,
                "",
                "",
                "",
                "",
                "ERROR: " + str(e)
            ]
            append_row(CSV_FILE, error_row)

            print(
                "[" + timestamp + "] "
                + str(user_id)
                + " ERROR: "
                + str(e)
            )

def main():
    ensure_csv_exists(CSV_FILE)
    print("Start polling every " + str(POLL_INTERVAL_SECONDS) + " seconds")

    while True:
        poll_once()
        time.sleep(POLL_INTERVAL_SECONDS)

if __name__ == "__main__":
    main()