import os
import json
import logging
from datetime import datetime
from telethon import TelegramClient
from dotenv import load_dotenv

load_dotenv()

API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")

client = TelegramClient("session", API_ID, API_HASH)

BASE_DIR = "data/raw"
IMAGE_DIR = os.path.join(BASE_DIR, "images")
LOG_DIR = "logs"

os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    filename=os.path.join(LOG_DIR, "scraper.log"),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

CHANNELS = {
    "chemed": "CheMed123",
    "lobelia": "lobelia4cosmetics",
    "tikvah_pharma": "tikvahpharma"
}

async def scrape_channel(channel_name, entity):
    today = datetime.today().strftime("%Y-%m-%d")

    output_dir = os.path.join(BASE_DIR, "telegram_messages", today)
    os.makedirs(output_dir, exist_ok=True)

    messages_data = []

    async for msg in client.iter_messages(entity, limit=1000):
        try:
            record = {
                "message_id": msg.id,
                "date": str(msg.date),
                "text": msg.message,
                "views": msg.views,
                "forwards": msg.forwards,
                "has_media": bool(msg.media)
            }

            # download image if exists
            if msg.photo:
                img_path = os.path.join(
                    IMAGE_DIR, channel_name, f"{msg.id}.jpg"
                )
                os.makedirs(os.path.dirname(img_path), exist_ok=True)
                await msg.download_media(file=img_path)
                record["image_path"] = img_path

            messages_data.append(record)

        except Exception as e:
            logging.error(f"Error in {channel_name} msg {msg.id}: {e}")

    # save JSON
    out_file = os.path.join(output_dir, f"{channel_name}.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(messages_data, f, indent=2)

    logging.info(f"Scraped {channel_name} with {len(messages_data)} messages")


async def main():
    await client.start()

    for key, channel in CHANNELS.items():
        try:
            logging.info(f"Scraping {channel}")
            entity = await client.get_entity(channel)
            print(f"Scraping: {entity.title}")
            await scrape_channel(key, entity)
        except Exception as e:
            logging.error(f"Failed channel {channel}: {e}")

    await client.disconnect()


with client:
    client.loop.run_until_complete(main())