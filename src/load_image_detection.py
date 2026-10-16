"""Idempotent load of YOLO detections into raw.image_detections."""

from __future__ import annotations

import ast
import json
import logging
from pathlib import Path
from typing import Any

import pandas as pd
from psycopg2.extras import execute_batch

from src.config import Settings, get_settings
from src.db import connection as db_connection
from src.logging_utils import configure_logging

logger = logging.getLogger(__name__)

UPSERT_SQL = """
INSERT INTO raw.image_detections (
    message_id,
    channel_name,
    image_path,
    detected_objects,
    image_category,
    max_confidence,
    loaded_at,
    updated_at
)
VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
ON CONFLICT (channel_name, message_id, image_path) DO UPDATE SET
    detected_objects = EXCLUDED.detected_objects,
    image_category = EXCLUDED.image_category,
    max_confidence = EXCLUDED.max_confidence,
    updated_at = NOW()
"""


def normalize_objects(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return json.dumps([])
    if isinstance(value, list):
        return json.dumps(value)
    text = str(value).strip()
    if not text:
        return json.dumps([])
    try:
        parsed = ast.literal_eval(text)
        if isinstance(parsed, list):
            return json.dumps(parsed)
    except (SyntaxError, ValueError):
        pass
    return json.dumps([item.strip() for item in text.split(",") if item.strip()])


def dataframe_to_rows(df: pd.DataFrame) -> list[tuple[Any, ...]]:
    rows: list[tuple[Any, ...]] = []
    for record in df.to_dict(orient="records"):
        message_id = record.get("message_id")
        if message_id is None or (isinstance(message_id, float) and pd.isna(message_id)):
            continue
        rows.append(
            (
                int(message_id),
                str(record.get("channel_name") or ""),
                str(record.get("image_path") or ""),
                normalize_objects(record.get("detected_objects")),
                record.get("image_category"),
                record.get("max_confidence") if not pd.isna(record.get("max_confidence")) else None,
            )
        )
    return rows


def load_detections(settings: Settings | None = None, csv_path: Path | None = None) -> int:
    cfg = settings or get_settings()
    configure_logging(cfg.log_level)
    path = csv_path or (cfg.data_processed_dir / "image_detections.csv")
    if not path.exists():
        logger.warning("Detections CSV not found: %s", path)
        return 0

    df = pd.read_csv(path)
    rows = dataframe_to_rows(df)
    if not rows:
        logger.warning("Detections CSV is empty")
        return 0

    with db_connection(cfg) as conn:
        with conn.cursor() as cursor:
            execute_batch(cursor, UPSERT_SQL, rows, page_size=200)
    logger.info("Loaded image detections", extra={"rows": len(rows)})
    return len(rows)


if __name__ == "__main__":
    load_detections()
