# Privacy, retention, and collection

This project is a portfolio pipeline for **public** Telegram channels that advertise medical and cosmetic products. It is not a consumer app and must not be used to scrape private chats, contacts, or personal profiles.

## Collection

- Live extraction uses the official Telegram API via Telethon and requires the operator's own `API_ID` / `API_HASH`.
- Default demo data is **synthetic**. It does not contain real usernames, phone numbers, or message IDs from production Telegram.
- Only channel posts are in scope. Do not extend the scraper to users, forwards graphs, or private groups.

## Retention

- Raw JSON and images live under `data/raw/` (gitignored).
- Warehouse rows keep `loaded_at` / `updated_at` for audit, not for profiling people.
- Operators should delete `data/raw`, `data/processed`, Telegram session files, and drop the database when a scrape is no longer needed.
- There is no built-in PII redaction. If a public post contains a phone number or name, treat the warehouse as sensitive.

## Access

- Analytics routes require `X-API-Key`.
- Do not expose Postgres ports on a public network without changing the default password.
- Never commit `.env`, `*.session`, or live extracts.

## Responsible use

- Follow [Telegram ToS](https://telegram.org/tos) and applicable law (including Ethiopia's data-protection rules if you operate there).
- This API is not a clinical or regulatory system. Product mentions are text tokens, not verified inventory or medical advice.
