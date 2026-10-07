"""Load sample placement records from sql/sample_data.sql into Supabase."""

import sys
from pathlib import Path

from db import get_connection

BASE_DIR = Path(__file__).resolve().parent
SAMPLE_DATA_PATH = BASE_DIR / "sql" / "sample_data.sql"


def main():
    if not SAMPLE_DATA_PATH.is_file():
        print(f"ERROR: Sample data file not found: {SAMPLE_DATA_PATH}")
        return 1

    try:
        sql = SAMPLE_DATA_PATH.read_text(encoding="utf-8")
        connection = get_connection()
    except Exception as error:
        print(f"ERROR preparing seed: {error}")
        return 1

    try:
        with connection.cursor() as cursor:
            cursor.execute(sql)
        connection.commit()
        print("SUCCESS: sample data loaded (10 students, 5 companies, 8 opportunities, 15 applications, 10 certificates).")
        return 0
    except Exception as error:
        connection.rollback()
        print(f"ERROR loading sample data: {error}")
        return 1
    finally:
        connection.close()


if __name__ == "__main__":
    sys.exit(main())