"""Create PostgreSQL connections to the project's Supabase database."""

import os
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def get_connection(cursor_factory=None):
    """Connect using the URL from .env and require an encrypted connection."""
    database_url = os.getenv("SUPABASE_DB_URL")
    if not database_url:
        raise RuntimeError("SUPABASE_DB_URL is missing; add it to the project .env file.")

    return psycopg2.connect(
        database_url,
        sslmode="require",
        cursor_factory=cursor_factory,
    )
