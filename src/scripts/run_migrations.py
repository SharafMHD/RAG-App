import os
import subprocess
import sys
from pathlib import Path

import psycopg2


LOCK_ID = 987654321
ALEMBIC_DIR = Path("/app/models/db_schemes/rag_app_db")


def _postgres_dsn() -> str:
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    db = os.getenv("POSTGRES_MAIN_DB", "rag_app_db")
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "admin")
    return f"host={host} port={port} dbname={db} user={user} password={password}"


def main() -> int:
    print("Running database migrations...", flush=True)
    connection = psycopg2.connect(_postgres_dsn())
    connection.autocommit = True
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_lock(%s)", (LOCK_ID,))
            try:
                result = subprocess.run(
                    ["alembic", "upgrade", "head"],
                    cwd=str(ALEMBIC_DIR),
                    check=False,
                )
                return result.returncode
            finally:
                cursor.execute("SELECT pg_advisory_unlock(%s)", (LOCK_ID,))
    finally:
        connection.close()


if __name__ == "__main__":
    sys.exit(main())
