"""Run SELECT statements from sql/queries.sql and print their result tables."""

import re
import sys
from pathlib import Path

from db import get_connection
from tabulate import tabulate

BASE_DIR = Path(__file__).resolve().parent
QUERIES_PATH = BASE_DIR / "sql" / "queries.sql"


def load_select_queries():
    """Load semicolon-separated queries and reject anything except SELECT."""
    sql_text = QUERIES_PATH.read_text(encoding="utf-8")
    sql_text = re.sub(r"--[^\n]*|/\*.*?\*/", "", sql_text, flags=re.DOTALL)
    queries = [statement.strip() for statement in sql_text.split(";") if statement.strip()]

    for index, query in enumerate(queries, start=1):
        if not re.match(r"(?is)^SELECT\b", query):
            raise ValueError(f"Query {index} is not a SELECT statement; refusing to run it.")

    return queries


def main():
    try:
        queries = load_select_queries()
        connection = get_connection()
    except Exception as error:
        print(f"ERROR: {error}")
        return 1

    had_errors = False
    try:
        connection.set_session(readonly=True)
        for index, query in enumerate(queries, start=1):
            try:
                with connection.cursor() as cursor:
                    cursor.execute(query)
                    rows = cursor.fetchall()
                    headers = [column[0] for column in cursor.description]
                print(f"\nQuery {index}")
                print(tabulate(rows, headers=headers, tablefmt="grid"))
                connection.rollback()
            except Exception as error:
                connection.rollback()
                had_errors = True
                print(f"ERROR in query {index}: {error}")
    finally:
        connection.close()

    return 1 if had_errors else 0


if __name__ == "__main__":
    sys.exit(main())
