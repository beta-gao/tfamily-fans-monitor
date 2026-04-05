import argparse
import os
from pathlib import Path

from db import import_csv_into_db, init_db


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_CSV_FILE = BASE_DIR / "tf_family_fans_multi.csv"
DEFAULT_DB_FILE = Path(os.environ.get("TF_DB_FILE", str(BASE_DIR / "tf_dashboard.sqlite3")))


def main():
    parser = argparse.ArgumentParser(description="Import legacy TF CSV data into SQLite.")
    parser.add_argument(
        "--csv",
        default=str(DEFAULT_CSV_FILE),
        help="Path to the legacy CSV file.",
    )
    parser.add_argument(
        "--db",
        default=str(DEFAULT_DB_FILE),
        help="Path to the SQLite database file.",
    )
    args = parser.parse_args()

    csv_path = Path(args.csv).expanduser().resolve()
    db_path = Path(args.db).expanduser().resolve()

    init_db(db_path)
    summary = import_csv_into_db(csv_path, db_path)

    print(f"Imported from CSV: {csv_path}")
    print(f"SQLite database: {db_path}")
    print(f"Valid CSV rows: {summary['csv_rows']}")
    print(f"Inserted rows: {summary['inserted_rows']}")
    print(f"Skipped rows: {summary['skipped_rows']}")


if __name__ == "__main__":
    main()
