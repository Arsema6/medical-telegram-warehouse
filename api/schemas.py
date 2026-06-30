from pydantic import BaseModel
from typing import Optional, List


class TopProduct(BaseModel):
    product: str
    count: int


class ChannelActivity(BaseModel):
    total_posts: int
    posts_per_day: List[dict]


class MessageSearch(BaseModel):
    message_id: int
    message_text: str


class VisualContent(BaseModel):
    images_per_channel: List[dict]
    promotional_count: int
    product_display_count: int