"""Check the database connection, server version, and public tables."""

from db import get_connection


def main():
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT version()")
            print("PostgreSQL version:")
            print(cursor.fetchone()[0])

            cursor.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
                ORDER BY table_name
                """
            )
            tables = [row[0] for row in cursor.fetchall()]
            print("\nTables in public schema:")
            if tables:
                for table_name in tables:
                    print(f"- {table_name}")
            else:
                print("(none yet; run python run_sql.py)")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
