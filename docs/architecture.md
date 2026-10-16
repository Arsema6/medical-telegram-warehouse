# Architecture

## Data flow

```text
Public Telegram channels
        │  Telethon (optional live scrape)
        ▼
JSON + images in data/raw  (data lake)
        │  idempotent upsert
        ▼
PostgreSQL raw schema
  raw.telegram_messages
  raw.image_detections
        │  dbt
        ▼
Star schema (public)
  dim_channels  dim_dates
        │            │
        └── fct_messages ── fct_image_detections
        │
        ▼
FastAPI (API key + rate limit)
        │
Dagster jobs: etl_pipeline (live) / demo_pipeline (seed)
```

## Layers

| Layer | Owner | Grain / notes |
| --- | --- | --- |
| Extract | `src/scraper.py` | Overwrites per-channel JSON for a scrape date. Re-runs are safe. |
| Load | `src/load_to_postgres.py` | Unique `(channel_name, message_id)`; updates views on conflict. |
| Transform | `medical_warehouse/` | Staging view + incremental facts. |
| Enrich | `src/yolo_detect.py` | Optional. Demo seed includes fixture detections. |
| Serve | `api/main.py` | Parameterized SQL only. |

Channel keys are MD5 hashes of `channel_name` so they stay stable when new channels appear (unlike `row_number()`).
