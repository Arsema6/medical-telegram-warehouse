"""Image-category rules used by YOLO enrichment (no model import required)."""

from __future__ import annotations

from collections.abc import Iterable

PRODUCT_OBJECTS = {
    "bottle",
    "cup",
    "cell phone",
    "book",
    "toothbrush",
    "handbag",
    "package",
    "box",
    "tv",
    "laptop",
}

IMAGE_CATEGORIES = ("promotional", "product_display", "lifestyle", "other")


def classify_image(objects: Iterable[str]) -> str:
    """Map detected COCO class names to a marketing-content category."""
    detected = {name.strip().lower() for name in objects if name}
    has_person = "person" in detected
    has_product = bool(detected.intersection(PRODUCT_OBJECTS))

    if has_person and has_product:
        return "promotional"
    if has_person and not has_product:
        return "lifestyle"
    if has_product and not has_person:
        return "product_display"
    return "other"
