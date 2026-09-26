"""Apply checked-in SQL migrations atomically with a checksum ledger."""

import argparse
import hashlib
import os
from pathlib import Path

import psycopg

MIGRATIONS = Path(__file__).resolve().parents[2] / "migrations"


def migrate(dsn: str, *, without_vectors: bool = False) -> None:
    if not dsn:
        raise ValueError("INDRA_DATABASE_URL is required")
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute("SELECT pg_advisory_lock(18527301)")
        try:
            conn.execute("""CREATE TABLE IF NOT EXISTS indra_schema_migrations (
                name text PRIMARY KEY, checksum text NOT NULL, without_vectors boolean NOT NULL,
                applied_at timestamptz NOT NULL DEFAULT now())""")
            for path in sorted(MIGRATIONS.glob("[0-9]*.sql")):
                source = path.read_text()
                checksum = hashlib.sha256(source.encode()).hexdigest()
                prior = conn.execute(
                    "SELECT checksum,without_vectors FROM indra_schema_migrations WHERE name=%s",
                    (path.name,),
                ).fetchone()
                if prior:
                    if prior != (checksum, without_vectors):
                        raise ValueError(
                            f"Applied migration or vector mode changed: {path.name}"
                        )
                    continue
                sql = source.replace("BEGIN;", "").replace("COMMIT;", "")
                if without_vectors:
                    sql = sql.replace("CREATE EXTENSION IF NOT EXISTS vector;", "")
                    sql = sql.replace(
                        "embedding vector,", "embedding double precision[],"
                    )
                with conn.transaction():
                    conn.execute(sql)
                    conn.execute(
                        "INSERT INTO indra_schema_migrations(name,checksum,without_vectors) VALUES (%s,%s,%s)",
                        (path.name, checksum, without_vectors),
                    )
        finally:
            conn.execute("SELECT pg_advisory_unlock(18527301)")


def main():
    from dotenv import load_dotenv

    load_dotenv()
    parser = argparse.ArgumentParser(description="Apply Indra database migrations")
    parser.add_argument(
        "--without-vectors",
        action="store_true",
        help="Use a nullable float array for unused embeddings on Postgres without pgvector",
    )
    args = parser.parse_args()
    migrate(os.getenv("INDRA_DATABASE_URL", ""), without_vectors=args.without_vectors)


if __name__ == "__main__":
    main()
