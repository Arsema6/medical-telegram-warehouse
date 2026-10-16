"""Telegram extraction into a local JSON data lake."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import date
from pathlib import Path
from typing import Any

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.config import Settings, get_settings
from src.logging_utils import configure_logging

logger = logging.getLogger(__name__)


def _write_json(path: Path, payload: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)


def serialize_message(
    *,
    message_id: int,
    channel_name: str,
    channel_type: str,
    message_date: str,
    text: str | None,
    views: int | None,
    forwards: int | None,
    has_media: bool,
    image_path: str | None = None,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "message_id": message_id,
        "channel_name": channel_name,
        "channel_type": channel_type,
        "date": message_date,
        "text": text,
        "views": views,
        "forwards": forwards,
        "has_media": has_media,
    }
    if image_path:
        record["image_path"] = image_path
    return record


@retry(
    reraise=True,
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=1, min=1, max=20),
    retry=retry_if_exception_type((ConnectionError, OSError, TimeoutError)),
)
async def scrape_channel(
    client: Any,
    channel: dict[str, str],
    *,
    settings: Settings,
    scrape_date: str | None = None,
) -> Path:
    """Pull messages for one channel and write a JSON file. Safe to re-run (overwrite)."""
    from telethon.errors import FloodWaitError

    key = channel["key"]
    entity_name = channel["entity"]
    channel_type = channel["type"]
    day = scrape_date or date.today().isoformat()
    output_dir = settings.data_raw_dir / "telegram_messages" / day
    image_root = settings.data_raw_dir / "images" / key
    messages_data: list[dict[str, Any]] = []

    try:
        entity = await client.get_entity(entity_name)
    except FloodWaitError as exc:
        logger.warning("Telegram flood wait for %s: %ss", entity_name, exc.seconds)
        await asyncio.sleep(int(exc.seconds) + 1)
        entity = await client.get_entity(entity_name)

    async for msg in client.iter_messages(entity, limit=settings.telegram_message_limit):
        try:
            image_path: str | None = None
            if getattr(msg, "photo", None):
                image_root.mkdir(parents=True, exist_ok=True)
                dest = image_root / f"{msg.id}.jpg"
                await msg.download_media(file=str(dest))
                image_path = str(dest.as_posix())

            messages_data.append(
                serialize_message(
                    message_id=int(msg.id),
                    channel_name=key,
                    channel_type=channel_type,
                    message_date=str(msg.date),
                    text=msg.message,
                    views=msg.views,
                    forwards=msg.forwards,
                    has_media=bool(msg.media),
                    image_path=image_path,
                )
            )
        except FloodWaitError as exc:
            logger.warning("Flood wait on message download: %ss", exc.seconds)
            await asyncio.sleep(int(exc.seconds) + 1)
        except Exception:
            logger.exception(
                "Failed to serialize message",
                extra={"channel": key, "message_id": getattr(msg, "id", None)},
            )

    out_file = output_dir / f"{key}.json"
    _write_json(out_file, messages_data)
    logger.info(
        "Wrote channel extract",
        extra={"channel": key, "rows": len(messages_data)},
    )
    return out_file


async def run_scrape_async(settings: Settings | None = None) -> None:
    from telethon import TelegramClient
    from telethon.errors import FloodWaitError, RPCError

    cfg = settings or get_settings()
    if not cfg.api_id or not cfg.api_hash:
        raise RuntimeError(
            "API_ID and API_HASH must be set to scrape Telegram. "
            "Use `python -m scripts.seed_demo` for a credentials-free demo."
        )

    client = TelegramClient(cfg.telegram_session_path, int(cfg.api_id), cfg.api_hash)
    channels = cfg.load_channels()
    async with client:
        for channel in channels:
            try:
                await scrape_channel(client, channel, settings=cfg)
            except (FloodWaitError, RPCError, ConnectionError, OSError):
                logger.exception(
                    "Skipping channel after retries", extra={"channel": channel.get("key")}
                )


def run_scrape(settings: Settings | None = None) -> None:
    cfg = settings or get_settings()
    configure_logging(cfg.log_level)
    asyncio.run(run_scrape_async(cfg))


if __name__ == "__main__":
    run_scrape()
