"""Measure real pipeline/API/dbt outcomes against the local database. Never invent metrics."""

from __future__ import annotations

import json
import statistics
import time
from datetime import UTC, datetime
from typing import Any

from fastapi.testclient import TestClient

from src.config import PROJECT_ROOT, get_settings
from src.db import connection
from src.image_classification import classify_image
from src.load_to_postgres import load_raw_messages

OUT_PATH = PROJECT_ROOT / "docs" / "engineering_outcomes.json"


def _count(sql: str) -> int:
    settings = get_settings()
    with connection(settings) as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql)
            value = cursor.fetchone()
            return int(value[0]) if value else 0


def measure_load() -> dict[str, float | int]:
    started = time.perf_counter()
    rows = load_raw_messages()
    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    started_dup = time.perf_counter()
    rows_second = load_raw_messages()
    dup_ms = round((time.perf_counter() - started_dup) * 1000, 2)
    stored = _count("SELECT COUNT(*) FROM raw.telegram_messages")
    return {
        "first_load_rows_processed": rows,
        "first_load_ms": elapsed_ms,
        "second_load_rows_processed": rows_second,
        "second_load_ms": dup_ms,
        "raw_telegram_messages_count": stored,
        "duplicate_row_delta": stored
        - _count(
            "SELECT COUNT(DISTINCT channel_name || ':' || message_id::text) "
            "FROM raw.telegram_messages"
        ),
    }


def measure_api(api_key: str) -> dict[str, Any]:
    from api.main import app

    client = TestClient(app)
    headers = {"X-API-Key": api_key}
    samples_ms: list[float] = []
    status_codes: dict[str, int] = {}
    paths = [
        "/health",
        "/api/reports/top-products?limit=5",
        "/api/search/messages?query=paracetamol&limit=10",
        "/api/reports/visual-content",
    ]
    for path in paths:
        started = time.perf_counter()
        response = client.get(path, headers=headers)
        samples_ms.append((time.perf_counter() - started) * 1000)
        status_codes[path] = response.status_code
    return {
        "request_count": len(paths),
        "latency_ms_mean": round(statistics.mean(samples_ms), 2),
        "latency_ms_p50": round(statistics.median(samples_ms), 2),
        "latency_ms_max": round(max(samples_ms), 2),
        "status_codes": status_codes,
    }


def measure_classifier() -> dict[str, Any]:
    cases = {
        "promotional": ["person", "bottle"],
        "lifestyle": ["person"],
        "product_display": ["bottle"],
        "other": ["chair"],
    }
    mismatches = {
        label: classify_image(objs)
        for label, objs in cases.items()
        if classify_image(objs) != label
    }
    return {
        "fixture_cases": len(cases),
        "mismatches": mismatches,
        "accuracy_on_fixtures": (len(cases) - len(mismatches)) / len(cases),
    }


def main() -> None:
    settings = get_settings()
    payload = {
        "collected_at_utc": datetime.now(UTC).isoformat(),
        "note": (
            "Measured on the machine that ran scripts/collect_engineering_outcomes.py "
            "after migrate + seed."
        ),
        "raw_table_counts": {
            "telegram_messages": _count("SELECT COUNT(*) FROM raw.telegram_messages"),
            "image_detections": _count("SELECT COUNT(*) FROM raw.image_detections"),
        },
        "idempotent_reload": measure_load(),
        "api": measure_api(settings.api_key),
        "image_category_rules": measure_classifier(),
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
