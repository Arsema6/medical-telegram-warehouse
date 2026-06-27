import os
import json
import psycopg2
from datetime import datetime

# -------------------------
# DB CONNECTION SETTINGS
# -------------------------
conn = psycopg2.connect(
    host="localhost",
    database="medical_warehouse",
    user="postgres",
    password="ballet1112",  # <-- change this
    port=5432
)

cursor = conn.cursor()

# -------------------------
# CREATE RAW TABLE (if not exists)
# -------------------------
cursor.execute("""
CREATE SCHEMA IF NOT EXISTS raw;

CREATE TABLE IF NOT EXISTS raw.telegram_messages (
    message_id BIGINT,
    channel_name TEXT,
    message_date TIMESTAMP,
    message_text TEXT,
    views INTEGER,
    forwards INTEGER,
    has_media BOOLEAN,
    image_path TEXT
);
""")

conn.commit()

# -------------------------
# PATH TO YOUR DATA LAKE
# -------------------------
BASE_PATH = "data/raw/telegram_messages"

# -------------------------
# LOAD JSON FILES
# -------------------------
for date_folder in os.listdir(BASE_PATH):
    date_path = os.path.join(BASE_PATH, date_folder)

    if not os.path.isdir(date_path):
        continue

    for file in os.listdir(date_path):
        if not file.endswith(".json"):
            continue

        channel_name = file.replace(".json", "")
        file_path = os.path.join(date_path, file)

        with open(file_path, "r", encoding="utf-8") as f:
            messages = json.load(f)

            for msg in messages:
                cursor.execute("""
                    INSERT INTO raw.telegram_messages (
                        message_id,
                        channel_name,
                        message_date,
                        message_text,
                        views,
                        forwards,
                        has_media,
                        image_path
                    )
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                """, (
                    msg.get("message_id"),
                    channel_name,
                    msg.get("date"),
                    msg.get("text"),
                    msg.get("views"),
                    msg.get("forwards"),
                    msg.get("has_media"),
                    msg.get("image_path")
                ))

        print(f"Loaded: {file_path}")

# -------------------------
# FINALIZE
# -------------------------
conn.commit()
cursor.close()
conn.close()

print("✅ Data successfully loaded into PostgreSQL")