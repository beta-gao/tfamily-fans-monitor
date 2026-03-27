import argparse
import csv
import shutil
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from zoneinfo import ZoneInfo


ISO_FORMAT = "%Y-%m-%d %H:%M:%S"
OFFSET_RE = re.compile(r"^([+-])(\d{2}):(\d{2})$")
DEFAULT_START_AT = "2026-03-27 00:00:00"


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Convert CSV timestamps from one timezone to another. "
            "Only rows whose 'time' column matches YYYY-MM-DD HH:mm:ss are changed."
        )
    )
    parser.add_argument("csv_file", help="Path to the CSV file to inspect or convert.")
    parser.add_argument(
        "--source-tz",
        default="UTC",
        help="Timezone currently used by the matching timestamps. Default: UTC.",
    )
    parser.add_argument(
        "--target-tz",
        default="America/New_York",
        help="Timezone to convert matching timestamps into. Default: America/New_York.",
    )
    parser.add_argument(
        "--start-at",
        default=DEFAULT_START_AT,
        help=(
            "Only convert rows whose matching timestamp is >= this value. "
            f"Format: YYYY-MM-DD HH:mm:ss. Default: {DEFAULT_START_AT}."
        ),
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write the converted timestamps back to the CSV in place.",
    )
    parser.add_argument(
        "--sample-limit",
        type=int,
        default=5,
        help="How many example conversions to print. Default: 5.",
    )
    return parser.parse_args()


def parse_iso_timestamp(value):
    try:
        return datetime.strptime(value, ISO_FORMAT)
    except ValueError:
        return None


def resolve_timezone(value):
    normalized = value.strip()
    if normalized.upper() == "UTC":
        return timezone.utc

    offset_match = OFFSET_RE.match(normalized)
    if offset_match:
        sign, hours, minutes = offset_match.groups()
        delta = timedelta(hours=int(hours), minutes=int(minutes))
        if sign == "-":
            delta = -delta
        return timezone(delta)

    try:
        return ZoneInfo(normalized)
    except Exception as exc:
        raise SystemExit(
            f"Unsupported timezone '{value}'. "
            "Use an IANA name like 'America/New_York' on Linux, or a fixed offset like '-04:00'."
        ) from exc


def iter_converted_rows(rows, source_tz, target_tz, start_at, sample_limit):
    converted = 0
    skipped_non_iso = 0
    skipped_before_start = 0
    samples = []

    for row in rows:
        original = (row.get("time") or "").strip()
        parsed = parse_iso_timestamp(original)
        if parsed is None:
            skipped_non_iso += 1
            yield row
            continue

        if start_at is not None and parsed < start_at:
            skipped_before_start += 1
            yield row
            continue

        converted_dt = parsed.replace(tzinfo=source_tz).astimezone(target_tz)
        converted_value = converted_dt.strftime(ISO_FORMAT)
        row["time"] = converted_value
        converted += 1

        if len(samples) < sample_limit:
            samples.append((original, converted_value))

        yield row

    return converted, skipped_non_iso, skipped_before_start, samples


def main():
    args = parse_args()
    csv_path = Path(args.csv_file).expanduser().resolve()
    if not csv_path.exists():
        raise SystemExit(f"CSV file not found: {csv_path}")

    source_tz = resolve_timezone(args.source_tz)
    target_tz = resolve_timezone(args.target_tz)
    start_at = None
    if args.start_at:
        start_at = parse_iso_timestamp(args.start_at)
        if start_at is None:
            raise SystemExit(f"Invalid --start-at value: {args.start_at}")

    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames
        if not fieldnames:
            raise SystemExit(f"CSV header is missing: {csv_path}")

        rows = list(reader)

    converted = 0
    skipped_non_iso = 0
    skipped_before_start = 0
    samples = []
    converted_rows = []

    generator = iter_converted_rows(rows, source_tz, target_tz, start_at, args.sample_limit)
    try:
        while True:
            converted_rows.append(next(generator))
    except StopIteration as stop:
        converted, skipped_non_iso, skipped_before_start, samples = stop.value

    print(f"File: {csv_path}")
    print(f"Source timezone: {args.source_tz}")
    print(f"Target timezone: {args.target_tz}")
    if args.start_at:
        print(f"Start-at filter: {args.start_at}")
    print(f"Converted ISO-format rows: {converted}")
    print(f"Skipped non-ISO rows: {skipped_non_iso}")
    print(f"Skipped before start-at: {skipped_before_start}")

    if samples:
        print("Sample conversions:")
        for before, after in samples:
            print(f"  {before} -> {after}")
    else:
        print("Sample conversions: none")

    if not args.write:
        print("Dry run only. Re-run with --write to modify the file.")
        return

    if converted == 0:
        print("No rows were changed. File left untouched.")
        return

    backup_path = csv_path.with_name(
        f"{csv_path.name}.bak-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    )
    shutil.copy2(csv_path, backup_path)

    with NamedTemporaryFile(
        "w",
        encoding="utf-8-sig",
        newline="",
        delete=False,
        dir=csv_path.parent,
    ) as tmp_handle:
        writer = csv.DictWriter(tmp_handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(converted_rows)
        tmp_path = Path(tmp_handle.name)

    tmp_path.replace(csv_path)
    print(f"Backup created: {backup_path}")
    print("CSV updated in place.")


if __name__ == "__main__":
    main()
