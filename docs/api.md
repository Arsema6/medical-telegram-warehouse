# API

Base URL: `http://localhost:8000`

Public (no key): `GET /health`, `/docs`, `/openapi.json`

Protected header: `X-API-Key: <API_KEY from .env>`

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/channels` | Dimension listing; optional `channel_type` |
| GET | `/api/channels/{channel_name}/activity` | Volume by `date_key` |
| GET | `/api/reports/top-products` | Token counts; `limit`, `channel_name` |
| GET | `/api/search/messages` | `query`, `limit`, `offset`, `sort=date\|views\|message_id`, `order` |
| GET | `/api/reports/visual-content` | Image counts and YOLO categories |

Sort and order are allow-listed. Message search binds `query` as a parameter (`ILIKE :q`); it is not concatenated into SQL.

Rate limit: `API_RATE_LIMIT_PER_MINUTE` (default 60) per client IP on `/api/*`.
