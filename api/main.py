"""FastAPI analytics service over the dbt star schema."""

from __future__ import annotations

import logging
import re
from collections import Counter
from typing import Any, Literal

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from api.database import get_db
from api.schemas import (
    CategoryCount,
    ChannelActivity,
    ChannelImageCount,
    ChannelListResponse,
    ChannelSummary,
    ErrorResponse,
    HealthResponse,
    MessageSearch,
    MessageSearchResponse,
    PostsPerDay,
    TopProduct,
    TopProductsResponse,
    VisualContent,
)
from api.security import rate_limiter, require_api_key
from src.config import get_settings
from src.logging_utils import configure_logging

STOPWORDS = {
    "the",
    "a",
    "an",
    "is",
    "and",
    "to",
    "of",
    "in",
    "for",
    "with",
    "on",
    "at",
    "from",
    "this",
    "that",
    "available",
    "pack",
}
TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z-]{2,}")
SORTABLE_SEARCH_COLUMNS = {
    "message_id": "f.message_id",
    "views": "f.view_count",
    "date": "f.date_key",
}

logger = logging.getLogger(__name__)
settings = get_settings()
configure_logging(settings.log_level)

ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Missing or invalid API key"},
    404: {"model": ErrorResponse, "description": "Resource not found"},
    422: {"model": ErrorResponse, "description": "Validation error"},
    429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
}

app = FastAPI(
    title="Medical Telegram Warehouse API",
    description=(
        "Read-only analytics over public Telegram medical-market posts. "
        "Send the `X-API-Key` header on all `/api/*` routes. "
        "Demo data is synthetic; live scrapes must follow Telegram ToS."
    ),
    version="1.1.0",
    contact={
        "name": "Project maintainers",
        "url": "https://github.com/Arsema6/medical-telegram-warehouse",
    },
)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    try:
        rate_limiter.check(request)
    except HTTPException as exc:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    return await call_next(request)


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_handler(_request: Request, exc: SQLAlchemyError) -> JSONResponse:
    logger.exception("Database error: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "detail": "Database query failed. Check that migrations and dbt models have been built."
        },
    )


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["ops"],
    summary="Liveness and database ping",
)
def health(db: Session = Depends(get_db)) -> HealthResponse:
    database_status: Literal["up", "down"] = "down"
    try:
        db.execute(text("SELECT 1"))
        database_status = "up"
    except SQLAlchemyError:
        logger.warning("Health check could not reach PostgreSQL")
    return HealthResponse(
        status="ok",
        service="medical-telegram-warehouse",
        database=database_status,
    )


@app.get(
    "/api/channels",
    response_model=ChannelListResponse,
    responses=ERROR_RESPONSES,
    tags=["channels"],
    summary="List channel dimension rows",
    dependencies=[Depends(require_api_key)],
)
def list_channels(
    db: Session = Depends(get_db),
    channel_type: str | None = Query(
        default=None,
        description="Filter by Medical, Cosmetics, or Pharmaceutical",
    ),
) -> ChannelListResponse:
    sql = """
        SELECT channel_name, channel_type, total_posts, avg_views
        FROM dim_channels
        WHERE (:channel_type IS NULL OR channel_type = :channel_type)
        ORDER BY total_posts DESC
    """
    rows = db.execute(text(sql), {"channel_type": channel_type}).fetchall()
    items = [
        ChannelSummary(
            channel_name=row[0],
            channel_type=row[1],
            total_posts=int(row[2] or 0),
            avg_views=float(row[3]) if row[3] is not None else None,
        )
        for row in rows
    ]
    return ChannelListResponse(items=items, count=len(items))


@app.get(
    "/api/reports/top-products",
    response_model=TopProductsResponse,
    responses=ERROR_RESPONSES,
    tags=["reports"],
    summary="Most frequent terms in message text",
    dependencies=[Depends(require_api_key)],
)
def top_products(
    db: Session = Depends(get_db),
    limit: int = Query(default=10, ge=1, le=100),
    channel_name: str | None = Query(default=None),
) -> TopProductsResponse:
    sql = """
        SELECT f.message_text
        FROM fct_messages f
        JOIN dim_channels c ON f.channel_key = c.channel_key
        WHERE (:channel_name IS NULL OR c.channel_name = :channel_name)
    """
    rows = db.execute(text(sql), {"channel_name": channel_name}).fetchall()
    counts: Counter[str] = Counter()
    scanned = 0
    for (message_text,) in rows:
        scanned += 1
        if not message_text:
            continue
        tokens = [
            tok.lower() for tok in TOKEN_RE.findall(message_text) if tok.lower() not in STOPWORDS
        ]
        counts.update(tokens)
    items = [TopProduct(term=term, count=count) for term, count in counts.most_common(limit)]
    return TopProductsResponse(
        items=items,
        limit=limit,
        total_messages_scanned=scanned,
    )


@app.get(
    "/api/channels/{channel_name}/activity",
    response_model=ChannelActivity,
    responses=ERROR_RESPONSES,
    tags=["channels"],
    summary="Posting volume for one channel",
    dependencies=[Depends(require_api_key)],
)
def channel_activity(channel_name: str, db: Session = Depends(get_db)) -> ChannelActivity:
    meta = db.execute(
        text(
            "SELECT channel_name, channel_type FROM dim_channels WHERE channel_name = :channel_name"
        ),
        {"channel_name": channel_name},
    ).fetchone()
    if meta is None:
        raise HTTPException(status_code=404, detail=f"Unknown channel_name: {channel_name}")

    total = db.execute(
        text("""
            SELECT COUNT(*) FROM fct_messages f
            JOIN dim_channels c ON f.channel_key = c.channel_key
            WHERE c.channel_name = :channel_name
            """),
        {"channel_name": channel_name},
    ).scalar()

    per_day = db.execute(
        text("""
            SELECT d.date_key, COUNT(*)
            FROM fct_messages f
            JOIN dim_channels c ON f.channel_key = c.channel_key
            JOIN dim_dates d ON f.date_key = d.date_key
            WHERE c.channel_name = :channel_name
            GROUP BY d.date_key
            ORDER BY d.date_key
            """),
        {"channel_name": channel_name},
    ).fetchall()

    return ChannelActivity(
        channel_name=meta[0],
        channel_type=meta[1],
        total_posts=int(total or 0),
        posts_per_day=[PostsPerDay(date_key=int(day), count=int(count)) for day, count in per_day],
    )


@app.get(
    "/api/search/messages",
    response_model=MessageSearchResponse,
    responses=ERROR_RESPONSES,
    tags=["search"],
    summary="Keyword search over fact messages",
    dependencies=[Depends(require_api_key)],
)
def search_messages(
    query: str = Query(..., min_length=2, max_length=120),
    db: Session = Depends(get_db),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=10000),
    sort: str = Query(default="date", pattern="^(date|views|message_id)$"),
    order: str = Query(default="desc", pattern="^(asc|desc)$"),
) -> MessageSearchResponse:
    sort_col = SORTABLE_SEARCH_COLUMNS[sort]
    order_sql = "ASC" if order == "asc" else "DESC"
    sql = f"""
        SELECT f.message_id, c.channel_name, f.message_text, f.view_count, f.date_key
        FROM fct_messages f
        JOIN dim_channels c ON f.channel_key = c.channel_key
        WHERE f.message_text ILIKE :q
        ORDER BY {sort_col} {order_sql}
        LIMIT :limit OFFSET :offset
    """
    rows = db.execute(
        text(sql),
        {"q": f"%{query}%", "limit": limit, "offset": offset},
    ).fetchall()
    items = [
        MessageSearch(
            message_id=int(row[0]),
            channel_name=row[1],
            message_text=row[2],
            view_count=int(row[3]) if row[3] is not None else None,
            message_date_key=int(row[4]) if row[4] is not None else None,
        )
        for row in rows
    ]
    return MessageSearchResponse(
        query=query,
        items=items,
        limit=limit,
        offset=offset,
        returned=len(items),
    )


@app.get(
    "/api/reports/visual-content",
    response_model=VisualContent,
    responses=ERROR_RESPONSES,
    tags=["reports"],
    summary="Image usage and YOLO category mix",
    dependencies=[Depends(require_api_key)],
)
def visual_content(db: Session = Depends(get_db)) -> VisualContent:
    image_rows = db.execute(text("""
            SELECT c.channel_name, COUNT(*)
            FROM fct_messages f
            JOIN dim_channels c ON f.channel_key = c.channel_key
            WHERE f.has_image = true
            GROUP BY c.channel_name
            ORDER BY COUNT(*) DESC
            """)).fetchall()
    categories = db.execute(text("""
            SELECT image_category, COUNT(*)
            FROM fct_image_detections
            GROUP BY image_category
            """)).fetchall()
    category_map = {row[0]: int(row[1]) for row in categories if row[0]}
    images_per_channel = [
        ChannelImageCount(channel=name, count=int(count)) for name, count in image_rows
    ]
    return VisualContent(
        images_per_channel=images_per_channel,
        category_counts=[
            CategoryCount(image_category=k, count=v) for k, v in sorted(category_map.items())
        ],
        promotional_count=category_map.get("promotional", 0),
        product_display_count=category_map.get("product_display", 0),
        lifestyle_count=category_map.get("lifestyle", 0),
        other_count=category_map.get("other", 0),
    )
