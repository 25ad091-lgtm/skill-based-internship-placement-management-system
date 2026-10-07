import os
from pathlib import Path

from psycopg2.extras import RealDictCursor
from db import get_connection
from werkzeug.security import generate_password_hash

BASE_DIR = Path(__file__).resolve().parent


def get_db_connection():
    return get_connection(cursor_factory=RealDictCursor)


def init_db():
    schema_path = BASE_DIR / "database" / "schema.sql"
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")

    with open(schema_path, "r", encoding="utf-8") as schema_file:
        sql = schema_file.read()

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
    finally:
        conn.close()


def ensure_default_admin():
    admin_email = os.getenv("ADMIN_EMAIL", "admin@skillplacement.edu")
    admin_password = (os.getenv("ADMIN_PASSWORD") or "").strip()
    placeholder_passwords = {"YOUR_ADMIN_PASSWORD", "REPLACE-WITH-A-STRONG-PASSWORD"}

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM users WHERE email = %s AND role = 'admin'",
                (admin_email,),
            )
            existing = cur.fetchone()
            if existing is None:
                if not admin_password or admin_password.upper() in placeholder_passwords:
                    print("Default admin not created; set a real ADMIN_PASSWORD in the project .env to enable bootstrap.")
                    return
                cur.execute(
                    """
                    INSERT INTO users (name, email, password_hash, role, department, phone)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        "System Administrator",
                        admin_email,
                        generate_password_hash(admin_password),
                        "admin",
                        "Administration",
                        "+91 00000 00000",
                    ),
                )
                conn.commit()
    finally:
        conn.close()
