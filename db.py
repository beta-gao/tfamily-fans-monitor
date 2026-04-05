import csv
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path


TIME_FORMAT = "%Y-%m-%d %H:%M:%S"
TIME_FORMATS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y/%m/%d %H:%M",
    "%Y/%m/%d %H:%M:%S",
)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS fan_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    captured_at TEXT NOT NULL,
    tag TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    nick_name TEXT,
    real_name TEXT,
    fans_num INTEGER,
    collect_num INTEGER,
    like_num INTEGER,
    error_message TEXT,
    UNIQUE(captured_at, user_id)
);

CREATE INDEX IF NOT EXISTS idx_fan_snapshots_captured_at
    ON fan_snapshots(captured_at);

CREATE INDEX IF NOT EXISTS idx_fan_snapshots_tag_captured_at
    ON fan_snapshots(tag, captured_at);

CREATE INDEX IF NOT EXISTS idx_fan_snapshots_user_captured_at
    ON fan_snapshots(user_id, captured_at);
"""

INSERT_SNAPSHOT_SQL = """
INSERT OR IGNORE INTO fan_snapshots (
    captured_at,
    tag,
    user_id,
    nick_name,
    real_name,
    fans_num,
    collect_num,
    like_num,
    error_message
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


def parse_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_time(value):
    if isinstance(value, datetime):
        return value

    for fmt in TIME_FORMATS:
        try:
            return datetime.strptime(str(value), fmt)
        except ValueError:
            continue
    return None


def normalize_timestamp(value):
    parsed = parse_time(value)
    if parsed is None:
        raise ValueError(f"Unsupported timestamp format: {value!r}")
    return parsed.strftime(TIME_FORMAT)


@contextmanager
def connect_db(db_path: Path):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA foreign_keys=ON")
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def init_db(db_path: Path):
    with connect_db(db_path) as connection:
        connection.executescript(SCHEMA_SQL)


def build_snapshot_record(
    *,
    captured_at,
    tag,
    user_id,
    nick_name="",
    real_name="",
    fans_num=None,
    collect_num=None,
    like_num=None,
    error_message=None,
):
    return (
        normalize_timestamp(captured_at),
        (tag or "").strip(),
        int(user_id),
        (nick_name or "").strip(),
        (real_name or "").strip(),
        parse_int(fans_num),
        parse_int(collect_num),
        parse_int(like_num),
        (error_message or "").strip() or None,
    )


def insert_snapshot(db_path: Path, snapshot):
    with connect_db(db_path) as connection:
        before = connection.total_changes
        connection.execute(INSERT_SNAPSHOT_SQL, snapshot)
        return connection.total_changes - before


def insert_snapshots(db_path: Path, snapshots):
    with connect_db(db_path) as connection:
        before = connection.total_changes
        connection.executemany(INSERT_SNAPSHOT_SQL, snapshots)
        return connection.total_changes - before


def load_dashboard_rows(db_path: Path, excluded_tags=(), active_user_ids=None):
    if not db_path.exists():
        return []

    excluded_tags = set(excluded_tags or ())
    active_user_ids = set(active_user_ids or ())
    rows = []

    with connect_db(db_path) as connection:
        result = connection.execute(
            """
            SELECT
                captured_at,
                tag,
                user_id,
                nick_name,
                real_name,
                fans_num,
                collect_num,
                like_num
            FROM fan_snapshots
            WHERE error_message IS NULL
              AND fans_num IS NOT NULL
            ORDER BY tag ASC, captured_at ASC
            """
        )

        for row in result:
            tag = (row["tag"] or "").strip()
            if not tag or tag in excluded_tags:
                continue

            parsed_time = parse_time(row["captured_at"])
            if parsed_time is None:
                continue

            user_id = row["user_id"]
            if active_user_ids and user_id not in active_user_ids:
                continue

            rows.append(
                {
                    "time": parsed_time,
                    "time_label": parsed_time.strftime(TIME_FORMAT),
                    "tag": tag,
                    "user_id": str(user_id).strip(),
                    "nick_name": (row["nick_name"] or "").strip(),
                    "real_name": (row["real_name"] or "").strip(),
                    "fans_num": row["fans_num"],
                    "collect_num": row["collect_num"],
                    "like_num": row["like_num"],
                }
            )

    return rows


def csv_row_to_snapshot(row):
    timestamp = (row.get("time") or "").strip()
    tag = (row.get("tag") or "").strip()
    user_id = parse_int(row.get("user_id"))

    if not timestamp or not tag or user_id is None:
        return None

    like_value = row.get("like_num")
    like_text = str(like_value).strip() if like_value is not None else ""
    error_message = like_text if like_text.startswith("ERROR:") else None

    return build_snapshot_record(
        captured_at=timestamp,
        tag=tag,
        user_id=user_id,
        nick_name=row.get("nick_name"),
        real_name=row.get("real_name"),
        fans_num=row.get("fans_num"),
        collect_num=row.get("collect_num"),
        like_num=None if error_message else like_value,
        error_message=error_message,
    )


def import_csv_into_db(csv_path: Path, db_path: Path):
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    snapshots = []
    skipped_rows = 0

    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            snapshot = csv_row_to_snapshot(row)
            if snapshot is None:
                skipped_rows += 1
                continue
            snapshots.append(snapshot)

    inserted_rows = insert_snapshots(db_path, snapshots)
    return {
        "csv_rows": len(snapshots),
        "inserted_rows": inserted_rows,
        "skipped_rows": skipped_rows,
    }
