# Medical Telegram Warehouse

End-to-end **medical-market analytics platform**: ingest public Telegram posts, land them in PostgreSQL, transform with dbt into a star schema, optionally enrich images with YOLOv8, and serve analytics through FastAPI.

The repo is a portfolio-grade ELT system for **data engineering, analytics engineering, backend, and ML/data platform** roles. A recruiter can run a full demo **without Telegram credentials** using synthetic seed data.

## Business problem

Ethiopia’s pharmacy and cosmetics trade is highly visible on public Telegram channels, but the market is fragmented: no shared catalog, inconsistent posting, and no structured view of products, activity, or creative style. Manual monitoring does not scale.

This platform turns those public posts into warehouse tables and a small analytics API so you can ask:

- Which product-like terms appear most often?
- How active is each channel, and on which days?
- How much of the content is image-led, and is it promotional vs product-display vs lifestyle?

It is **not** a clinical system, a price index, or a scraper for private chats.

## Architecture

```text
┌──────────────┐   Telethon    ┌─────────────┐  upsert   ┌─────────────────────┐
│ Public TG    │ ────────────► │ Data lake   │ ────────► │ PostgreSQL (raw)    │
│ channels     │   (optional)  │ JSON+images │           │ telegram_messages   │
└──────────────┘               └─────────────┘           │ image_detections    │
                                                         └──────────┬──────────┘
                                                                dbt │
                                                         ┌──────────▼──────────┐
                                                         │ Star schema         │
                                                         │ dim_channels        │
                                                         │ dim_dates           │
                                                         │ fct_messages        │
                                                         │ fct_image_detections│
                                                         └──────────┬──────────┘
                               ┌─────────────┐                      │
                               │ YOLOv8      │ ─ optional CSV ──────┤
                               └─────────────┘                      │
                                                         ┌──────────▼──────────┐
                         Dagster (etl | demo)            │ FastAPI + API key   │
                                                         └─────────────────────┘
```

More detail: [docs/architecture.md](docs/architecture.md).

### Why these tools

| Choice | Role | Rationale |
| --- | --- | --- |
| Telethon | Extract | Official Telegram API; no HTML scraping. |
| PostgreSQL | System of record | Constraints, upserts, and dbt-postgres. |
| dbt | Transform | Testable SQL, sources, incremental facts. |
| Dagster | Orchestrate | Explicit job graph for scrape → load → dbt → YOLO. |
| YOLOv8n | Enrich | Lightweight COCO detector mapped to marketing categories. Optional in demo/CI. |
| FastAPI | Serve | Typed contracts, OpenAPI, dependency-injected DB sessions. |
| Docker Compose | Run | Postgres + API (and optional Dagster) from a clean machine. |

## Star schema

**Dimensions**

- `dim_channels` — one row per channel (`channel_key` = MD5 of `channel_name`, plus type and activity stats)
- `dim_dates` — one row per observed calendar day (`date_key` = `YYYYMMDD`)

**Facts**

- `fct_messages` — one row per channel + Telegram `message_id` (incremental on `updated_at`)
- `fct_image_detections` — one row per image joined to the message fact (incremental on detection `updated_at`)

Raw grain is preserved in `raw.telegram_messages` with `UNIQUE (channel_name, message_id)` so loaders are idempotent.

## Local setup

### Prerequisites

- Python 3.11+
- Docker (recommended) **or** local PostgreSQL 15+
- Telegram API credentials **only** if you scrape live channels ([my.telegram.org](https://my.telegram.org))

### 1. Clone and environment

```bash
git clone https://github.com/Arsema6/medical-telegram-warehouse.git
cd medical-telegram-warehouse
cp .env.example .env
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
```

`.env.example` documents every variable. Do not commit `.env`. Default local credentials are `warehouse` / `warehouse` and are for **localhost only**.

### 2. Database and demo warehouse (no Telegram)

```bash
docker compose up -d postgres
python -m scripts.migrate
python -m scripts.seed_demo
dbt run --project-dir medical_warehouse --profiles-dir medical_warehouse
dbt test --project-dir medical_warehouse --profiles-dir medical_warehouse
uvicorn api.main:app --reload --port 8000
```

Open [http://localhost:8000/docs](http://localhost:8000/docs). Send header `X-API-Key: dev-api-key-change-me` (or the value in your `.env`).

`scripts.migrate` applies every file in `db/migrations/` in lexical order, tracking applied files in `raw.schema_migrations`, so re-running it is a no-op. `000_reconcile_legacy.sql` runs first and heals databases created before migrations existed (adds missing columns, fixes the `message_date` type, collapses duplicate keys, and rebuilds indexes/constraints); on a fresh database it does nothing.

### 3. One-command Docker demo

```bash
cp .env.example .env
docker compose up --build
```

This starts Postgres, applies migrations, loads synthetic demo data, and serves the API on port 8000. Dagster is optional:

```bash
docker compose --profile full up --build
```

Dagster UI: [http://localhost:3000](http://localhost:3000). Run `demo_pipeline` (seed + dbt + detections) or `etl_pipeline` (live scrape; needs `API_ID` / `API_HASH`).

## Pipeline execution

### Demo (recommended for reviewers)

```bash
python -m scripts.migrate
python -m scripts.seed_demo
dbt run --project-dir medical_warehouse --profiles-dir medical_warehouse
dbt test --project-dir medical_warehouse --profiles-dir medical_warehouse
```

Or: `dagster dev -f pipeline.py` → job `demo_pipeline`.

### Live Telegram (optional)

1. Set `API_ID` and `API_HASH` in `.env`.
2. Channels live in `config/channels.yaml` (not hardcoded in SQL).
3. `python -m src.scraper` writes `data/raw/telegram_messages/<date>/<channel>.json`.
4. `python -m src.load_to_postgres` upserts into `raw.telegram_messages`.
5. `dbt run` / `dbt test`.
6. YOLO (needs `pip install -r requirements-ml.txt` and `SKIP_YOLO=0`):

```bash
python -m src.yolo_detect
python -m src.load_image_detection
dbt run --select fct_image_detections
```

Re-running loaders **does not duplicate** messages or detections; they `ON CONFLICT ... DO UPDATE`.

## API usage

Docs: [docs/api.md](docs/api.md). Examples assume the default demo key.

```bash
curl -s http://localhost:8000/health

curl -s -H "X-API-Key: dev-api-key-change-me" \
  "http://localhost:8000/api/reports/top-products?limit=10"

curl -s -H "X-API-Key: dev-api-key-change-me" \
  "http://localhost:8000/api/channels/chemed/activity"

curl -s -H "X-API-Key: dev-api-key-change-me" \
  "http://localhost:8000/api/search/messages?query=paracetamol&limit=10&sort=views&order=desc"

curl -s -H "X-API-Key: dev-api-key-change-me" \
  "http://localhost:8000/api/reports/visual-content"
```

Invalid keys return 401. Unknown channels return 404. Sort/order are allow-listed; filters are bound parameters.

## Testing and CI

```bash
black --check src api scripts tests pipeline.py
ruff check src api scripts tests pipeline.py
mypy src api scripts
python -m pytest tests/ -v
dbt compile --project-dir medical_warehouse --profiles-dir medical_warehouse
dbt test --project-dir medical_warehouse --profiles-dir medical_warehouse
dbt source freshness --project-dir medical_warehouse --profiles-dir medical_warehouse
docker build -t medical-telegram-warehouse:local .
```

Pytest mocks Telegram and the API database. Tests marked `integration` run against Postgres when it is reachable (GitHub Actions always starts a service). CI workflow: `.github/workflows/ci.yml` runs black/ruff/mypy, migrate + seed, pytest, dbt debug/compile/run/test/freshness, a Docker build, and `docker compose config`.

## Security and privacy

- Secrets only from the environment (`.env` gitignored; Telegram sessions gitignored).
- Analytics routes require `X-API-Key`; `/health` and OpenAPI stay public.
- In-process rate limit on `/api/*`.
- Search uses parameterized `ILIKE`; sort columns are not taken from raw strings.
- Privacy and retention: [docs/privacy.md](docs/privacy.md).

## Engineering outcomes

Numbers below are **measured**, not targets. They come from this repository’s synthetic demo seed and unit tests, captured with `scripts/collect_engineering_outcomes.py`. YOLO mAP is **not** reported: the demo does not ship labeled medical-product images or a training run.

### Measured results

| Measurement | Result | How it was measured |
| --- | --- | --- |
| Demo messages loaded | 13 raw rows, 13 distinct message keys | `raw.telegram_messages` after `seed_demo` |
| Demo detections loaded | 6 raw rows | `raw.image_detections` after `seed_demo` |
| Loader idempotency | Re-running the loader kept 13 rows (`duplicate_row_delta = 0`) | `load_raw_messages()` executed twice |
| Loader wall-clock | 159 ms first load, 151 ms reload (13 rows, upsert) | timed around `load_raw_messages()` |
| API contract tests | 13 tests: auth, 404s, limit/param validation, sort allow-list, response models | `tests/test_api.py` |
| Image-category rules | 4/4 fixture cases correct (promotional, lifestyle, product_display, other) | `tests/test_image_classification.py` + collect script |
| API latency (TestClient) | p50 28 ms, mean 209 ms, max 757 ms over 4 endpoints | `scripts/collect_engineering_outcomes.py`; the mean is inflated by a one-off first-call warmup |
| Full test suite | 39 tests pass | `python -m pytest tests/` |
| dbt | 5 models, 43 data tests pass; source freshness PASS | `dbt run` / `dbt test` / `dbt source freshness` |

Environment for the numbers above: Windows, Python 3.14, PostgreSQL 18.6 (local server). Docker Compose pins `postgres:15`, so absolute timings will differ on other machines.

### Re-measure on your own database

The committed numbers are regenerated (and `docs/engineering_outcomes.json` overwritten) by:

```bash
python -m scripts.migrate
python -m scripts.seed_demo
python -m scripts.collect_engineering_outcomes
```

`docs/engineering_outcomes.json` is the committed source of truth for load milliseconds, SQL row counts, and TestClient latency on the machine that produced it.

## Limitations and next steps

- Live scrape coverage is three public channels; demo data is synthetic.
- Token “products” are whitespace words, not a curated drug ontology or NER model.
- YOLOv8n is COCO-pretrained; bottles/people are proxies, not SKU recognition.
- Rate limiting is in-process (not Redis); fine for a single API replica.
- No streaming CDC; batch ELT with incremental dbt facts.
- Useful follow-ons: Amharic-aware tokenization, price extraction, Slack/Pager alerts on dbt test failure, and a real image-eval set if you fine-tune YOLO.

## License

Educational / portfolio use. Respect Telegram’s terms and local law when collecting live data.
