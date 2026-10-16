# dbt project: medical_warehouse

Star-schema transforms over `raw.telegram_messages` and `raw.image_detections`.

## Layout

- `models/staging` — cleaned message grain (`stg_telegram_messages`)
- `models/marts` — `dim_channels`, `dim_dates`, `fct_messages`, `fct_image_detections`
- `tests` — warehouse assertions (no future dates, non-negative views)

## Commands

From the repository root:

```bash
dbt debug --project-dir medical_warehouse --profiles-dir medical_warehouse
dbt run --project-dir medical_warehouse --profiles-dir medical_warehouse
dbt test --project-dir medical_warehouse --profiles-dir medical_warehouse
dbt docs generate --project-dir medical_warehouse --profiles-dir medical_warehouse
```

Connection settings come from `DB_*` environment variables (see `.env.example`).
