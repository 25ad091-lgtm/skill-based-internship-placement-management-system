"""Run numbered SQL scripts, committing or rolling back each file separately."""

import re
import sys
from pathlib import Path

from db import get_connection

BASE_DIR = Path(__file__).resolve().parent
SQL_DIR = BASE_DIR / "sql"


def main():
    # Keep migration order numeric, and include the optional RLS script (07).
    scripts = sorted(
        path for path in SQL_DIR.glob("*.sql")
        if re.match(r"^0[1-7]_.*\.sql$", path.name)
    )
    if not scripts:
        print(f"ERROR: No numbered SQL files found in {SQL_DIR}")
        return 1

    try:
        connection = get_connection()
    except Exception as error:
        print(f"ERROR connecting to database: {error}")
        return 1

    had_errors = False
    try:
        for script_path in scripts:
            try:
                sql = script_path.read_text(encoding="utf-8")
                with connection.cursor() as cursor:
                    cursor.execute(sql)
                connection.commit()
                print(f"SUCCESS {script_path.name}")
            except Exception as error:
                connection.rollback()
                had_errors = True
                print(f"ERROR {script_path.name}: {error}")
    finally:
        connection.close()

    return 1 if had_errors else 0


if __name__ == "__main__":
    sys.exit(main())
