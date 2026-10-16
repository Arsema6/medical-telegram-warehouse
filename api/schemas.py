"""Pydantic request and response models for the analytics API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    detail: str


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str
    database: Literal["up", "down"]


class TopProduct(BaseModel):
    term: str = Field(description="Normalized token extracted from message text")
    count: int = Field(ge=0)


class TopProductsResponse(BaseModel):
    items: list[TopProduct]
    limit: int
    total_messages_scanned: int


class PostsPerDay(BaseModel):
    date_key: int
    count: int


class ChannelActivity(BaseModel):
    channel_name: str
    channel_type: str | None = None
    total_posts: int
    posts_per_day: list[PostsPerDay]


class ChannelSummary(BaseModel):
    channel_name: str
    channel_type: str | None = None
    total_posts: int
    avg_views: float | None = None


class ChannelListResponse(BaseModel):
    items: list[ChannelSummary]
    count: int


class MessageSearch(BaseModel):
    message_id: int
    channel_name: str
    message_text: str | None = None
    view_count: int | None = None
    message_date_key: int | None = None


class MessageSearchResponse(BaseModel):
    query: str
    items: list[MessageSearch]
    limit: int
    offset: int
    returned: int


class ChannelImageCount(BaseModel):
    channel: str
    count: int


class CategoryCount(BaseModel):
    image_category: str
    count: int


class VisualContent(BaseModel):
    images_per_channel: list[ChannelImageCount]
    category_counts: list[CategoryCount]
    promotional_count: int
    product_display_count: int
    lifestyle_count: int
    other_count: int
