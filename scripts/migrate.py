"""Apply SQL migrations in db/migrations in lexical order."""

from __future__ import annotations

import logging

from src.config import PROJECT_ROOT, get_settings
from src.db import connection
from src.logging_utils import configure_logging

logger = logging.getLogger(__name__)
MIGRATIONS_DIR = PROJECT_ROOT / "db" / "migrations"


def apply_migrations() -> list[str]:
    settings = get_settings()
    configure_logging(settings.log_level)
    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not files:
        raise FileNotFoundError(f"No SQL files in {MIGRATIONS_DIR}")

    applied: list[str] = []
    with connection(settings) as conn:
        with conn.cursor() as cursor:
            cursor.execute("CREATE SCHEMA IF NOT EXISTS raw")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS raw.schema_migrations (
                    filename TEXT PRIMARY KEY,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """)
            cursor.execute("SELECT filename FROM raw.schema_migrations")
            done = {row[0] for row in cursor.fetchall()}
            for path in files:
                if path.name in done:
                    logger.info("Skipping applied migration %s", path.name)
                    continue
                cursor.execute(path.read_text(encoding="utf-8"))
                cursor.execute(
                    "INSERT INTO raw.schema_migrations (filename) VALUES (%s)",
                    (path.name,),
                )
                applied.append(path.name)
                logger.info("Applied migration %s", path.name)
    return applied


def main() -> None:
    applied = apply_migrations()
    print(f"Applied migrations: {applied or 'none (already up to date)'}")


if __name__ == "__main__":
    main()
