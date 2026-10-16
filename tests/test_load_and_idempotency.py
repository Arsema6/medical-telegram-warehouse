from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.load_image_detection import dataframe_to_rows, normalize_objects
from src.load_to_postgres import UPSERT_SQL, iter_message_files, row_from_message
from tests.conftest import postgres_available


def test_row_from_message_uses_channel_fallback() -> None:
    row = row_from_message(
        {
            "message_id": 1,
            "date": "2024-06-01T00:00:00+00:00",
            "text": "Paracetamol",
            "views": 10,
            "forwards": 0,
            "has_media": False,
        },
        "chemed",
    )
    assert row[0] == 1
    assert row[1] == "chemed"


def test_upsert_sql_is_idempotent() -> None:
    assert "ON CONFLICT (channel_name, message_id)" in UPSERT_SQL
    assert "DO UPDATE" in UPSERT_SQL


def test_iter_message_files_reads_nested_json(tmp_path: Path) -> None:
    folder = tmp_path / "2024-06-01"
    folder.mkdir()
    (folder / "chemed.json").write_text("[]", encoding="utf-8")
    (folder / "ignore.txt").write_text("nope", encoding="utf-8")
    files = iter_message_files(tmp_path)
    assert [path.name for path in files] == ["chemed.json"]


def test_normalize_objects_parses_list_string() -> None:
    assert json.loads(normalize_objects("['bottle', 'person']")) == ["bottle", "person"]


def test_dataframe_to_rows_skips_null_message_id() -> None:
    import pandas as pd

    df = pd.DataFrame(
        [
            {
                "message_id": None,
                "channel_name": "chemed",
                "image_path": "x.jpg",
                "detected_objects": "[]",
                "image_category": "other",
                "max_confidence": None,
            }
        ]
    )
    assert dataframe_to_rows(df) == []


@pytest.mark.integration
@pytest.mark.skipif(not postgres_available(), reason="PostgreSQL is not reachable")
def test_message_upsert_does_not_duplicate() -> None:
    from scripts.migrate import apply_migrations
    from src.config import get_settings
    from src.db import connection
    from src.load_to_postgres import upsert_messages

    apply_migrations()
    settings = get_settings()
    row = (
        999001,
        "chemed",
        "Medical",
        "2024-06-01T00:00:00+00:00",
        "Idempotency probe paracetamol",
        1,
        0,
        False,
        None,
    )
    with connection(settings) as conn:
        upsert_messages(conn, [row])
        upsert_messages(conn, [row])
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*) FROM raw.telegram_messages
                WHERE channel_name = %s AND message_id = %s
                """,
                ("chemed", 999001),
            )
            count = cursor.fetchone()[0]
            # Keep the operator's database clean after the probe.
            cursor.execute(
                "DELETE FROM raw.telegram_messages WHERE channel_name = %s AND message_id = %s",
                ("chemed", 999001),
            )
    assert count == 1
