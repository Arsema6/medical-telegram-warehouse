from pathlib import Path

import pytest

from src.config import PROJECT_ROOT
from tests.conftest import postgres_available

MIGRATIONS_DIR = PROJECT_ROOT / "db" / "migrations"
INIT_SQL = (MIGRATIONS_DIR / "001_init.sql").read_text(encoding="utf-8")
RECONCILE_SQL = (MIGRATIONS_DIR / "000_reconcile_legacy.sql").read_text(encoding="utf-8")


def test_raw_tables_have_keys_and_timestamps() -> None:
    assert "UNIQUE (channel_name, message_id)" in INIT_SQL
    assert "PRIMARY KEY" in INIT_SQL
    assert "FOREIGN KEY (channel_name, message_id)" in INIT_SQL
    assert "loaded_at TIMESTAMPTZ" in INIT_SQL
    assert "updated_at TIMESTAMPTZ" in INIT_SQL
    assert "CREATE INDEX" in INIT_SQL


def test_migrations_run_in_lexical_order() -> None:
    names = sorted(path.name for path in MIGRATIONS_DIR.glob("*.sql"))
    assert names[0] == "000_reconcile_legacy.sql"
    assert "001_init.sql" in names


def test_reconcile_migration_is_guarded_and_idempotent() -> None:
    # Guards keep the reconcile migration a no-op on a fresh database.
    assert "information_schema.tables" in RECONCILE_SQL
    assert "ADD COLUMN IF NOT EXISTS" in RECONCILE_SQL
    assert "CREATE INDEX IF NOT EXISTS" in RECONCILE_SQL
    assert "pg_constraint" in RECONCILE_SQL


def test_demo_data_is_synthetic_and_present() -> None:
    demo = PROJECT_ROOT / "data" / "demo" / "telegram_messages" / "2024-06-01"
    files = list(demo.glob("*.json"))
    assert len(files) == 3
    detections = Path(PROJECT_ROOT / "data" / "demo" / "image_detections.csv")
    assert detections.exists()
    text = detections.read_text(encoding="utf-8")
    assert "promotional" in text


@pytest.mark.integration
@pytest.mark.skipif(not postgres_available(), reason="PostgreSQL is not reachable")
def test_migrations_are_idempotent() -> None:
    from scripts.migrate import apply_migrations

    apply_migrations()  # brings the database to head (no-op if already there)
    assert apply_migrations() == []  # nothing left to apply on a second run
