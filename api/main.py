from fastapi import FastAPI, Query
from api.database import SessionLocal
from sqlalchemy import text
from collections import Counter
import re

app = FastAPI()
STOPWORDS = {"the", "a", "is", "and", "to", "of", "in"}

# -------------------------
# Endpoint 1
# -------------------------
@app.get("/api/reports/top-products")
def top_products():
    db = SessionLocal()
    rows = db.execute(text("SELECT message_text FROM fct_messages")).fetchall()

    words = []
    for r in rows:
        if r[0]:
            tokens = re.findall(r"\w+", r[0].lower())
            words.extend([t for t in tokens if t not in STOPWORDS])

    counts = Counter(words).most_common(10)

    return [{"product": w, "count": c} for w, c in counts]


# -------------------------
# Endpoint 2
# Channel activity
# -------------------------
@app.get("/api/channels/{channel_name}/activity")
def channel_activity(channel_name: str):
    db = SessionLocal()

    total = db.execute(text("""
        SELECT COUNT(*) FROM fct_messages f
        JOIN dim_channels c ON f.channel_key = c.channel_key
        WHERE c.channel_name = :channel_name
    """), {"channel_name": channel_name}).scalar()

    per_day = db.execute(text("""
        SELECT d.date_key, COUNT(*) 
        FROM fct_messages f
        JOIN dim_channels c ON f.channel_key = c.channel_key
        JOIN dim_dates d ON f.date_key = d.date_key
        WHERE c.channel_name = :channel_name
        GROUP BY d.date_key
        ORDER BY d.date_key
    """), {"channel_name": channel_name}).fetchall()

    return {
        "total_posts": total,
        "posts_per_day": [{"date": d, "count": c} for d, c in per_day]
    }


# -------------------------
# Endpoint 3
# -------------------------
@app.get("/api/search/messages")
def search_messages(query: str = Query(...)):
    db = SessionLocal()

    result = db.execute(text("""
        SELECT message_id, message_text
        FROM fct_messages
        WHERE message_text ILIKE :q
        LIMIT 50
    """), {"q": f"%{query}%"}).fetchall()

    return [
        {"message_id": r[0], "message_text": r[1]}
        for r in result
    ]


# -------------------------
# Endpoint 4
# -------------------------
@app.get("/api/reports/visual-content")
def visual_content():
    db = SessionLocal()

    images_per_channel = db.execute(text("""
        SELECT c.channel_name, COUNT(*)
        FROM fct_messages f
        JOIN dim_channels c ON f.channel_key = c.channel_key
        WHERE f.image_path IS NOT NULL
        GROUP BY c.channel_name
    """)).fetchall()

    promotional = db.execute(text("""
        SELECT COUNT(*) FROM fct_image_detections
        WHERE image_category = 'promotional'
    """)).scalar() or 0

    product_display = db.execute(text("""
        SELECT COUNT(*) FROM fct_image_detections
        WHERE image_category = 'product_display'
    """)).scalar() or 0

    return {
        "images_per_channel": [
            {"channel": c, "count": n} for c, n in images_per_channel
        ],
        "promotional_count": promotional,
        "product_display_count": product_display
    }