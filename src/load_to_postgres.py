"""Idempotent load of JSON extracts into raw.telegram_messages."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from psycopg2.extensions import connection as PgConnection
from psycopg2.extras import execute_batch

from src.config import Settings, get_settings
from src.db import connection as db_connection
from src.logging_utils import configure_logging

logger = logging.getLogger(__name__)

UPSERT_SQL = """
INSERT INTO raw.telegram_messages (
    message_id,
    channel_name,
    channel_type,
    message_date,
    message_text,
    views,
    forwards,
    has_media,
    image_path,
    loaded_at,
    updated_at
)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
ON CONFLICT (channel_name, message_id) DO UPDATE SET
    channel_type = EXCLUDED.channel_type,
    message_date = EXCLUDED.message_date,
    message_text = EXCLUDED.message_text,
    views = EXCLUDED.views,
    forwards = EXCLUDED.forwards,
    has_media = EXCLUDED.has_media,
    image_path = COALESCE(EXCLUDED.image_path, raw.telegram_messages.image_path),
    updated_at = NOW()
"""


def row_from_message(msg: dict[str, Any], channel_name: str) -> tuple[Any, ...]:
    return (
        msg.get("message_id"),
        msg.get("channel_name") or channel_name,
        msg.get("channel_type"),
        msg.get("date"),
        msg.get("text"),
        msg.get("views"),
        msg.get("forwards"),
        msg.get("has_media"),
        msg.get("image_path"),
    )


def iter_message_files(base_path: Path) -> list[Path]:
    if not base_path.exists():
        return []
    files: list[Path] = []
    for date_folder in sorted(base_path.iterdir()):
        if not date_folder.is_dir():
            continue
        files.extend(sorted(date_folder.glob("*.json")))
    return files


def upsert_messages(conn: PgConnection, rows: list[tuple[Any, ...]]) -> int:
    if not rows:
        return 0
    with conn.cursor() as cursor:
        execute_batch(cursor, UPSERT_SQL, rows, page_size=500)
    return len(rows)


def load_raw_messages(settings: Settings | None = None, base_path: Path | None = None) -> int:
    cfg = settings or get_settings()
    configure_logging(cfg.log_level)
    root = base_path or (cfg.data_raw_dir / "telegram_messages")
    files = iter_message_files(root)
    if not files:
        logger.warning("No JSON extracts found under %s", root)
        return 0

    total = 0
    with db_connection(cfg) as conn:
        for file_path in files:
            channel_name = file_path.stem
            with file_path.open(encoding="utf-8") as handle:
                messages = json.load(handle)
            if not isinstance(messages, list):
                raise ValueError(f"Expected a JSON list in {file_path}")
            rows = [row_from_message(msg, channel_name) for msg in messages]
            total += upsert_messages(conn, rows)
            logger.info("Loaded extract", extra={"channel": channel_name, "rows": len(rows)})
    logger.info("Finished raw message load", extra={"rows": total})
    return total


if __name__ == "__main__":
    load_raw_messages()
