"""Run YOLOv8 over downloaded images and write a detections CSV."""

from __future__ import annotations

import logging
from collections import defaultdict
from pathlib import Path
from typing import Any

import pandas as pd

from src.config import Settings, get_settings
from src.image_classification import classify_image
from src.logging_utils import configure_logging

logger = logging.getLogger(__name__)
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def extract_message_id(path: Path) -> str:
    return path.stem


def detections_from_results(
    image_path: Path, objects: list[str], confidences: list[float]
) -> dict[str, Any]:
    unique_objects = sorted(set(objects))
    return {
        "image_path": str(image_path.as_posix()),
        "channel_name": image_path.parent.name,
        "message_id": extract_message_id(image_path),
        "detected_objects": unique_objects,
        "image_category": classify_image(unique_objects),
        "max_confidence": max(confidences) if confidences else None,
    }


def collect_image_paths(image_dir: Path) -> list[Path]:
    if not image_dir.exists():
        return []
    return [
        path
        for path in sorted(image_dir.rglob("*"))
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    ]


def run_yolo_detection(settings: Settings | None = None, model: Any | None = None) -> Path:
    cfg = settings or get_settings()
    configure_logging(cfg.log_level)
    image_dir = cfg.data_raw_dir / "images"
    output_dir = cfg.data_processed_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "image_detections.csv"

    paths = collect_image_paths(image_dir)
    if not paths:
        logger.warning("No images found under %s; writing empty detections file", image_dir)
        pd.DataFrame(
            columns=[
                "image_path",
                "channel_name",
                "message_id",
                "detected_objects",
                "image_category",
                "max_confidence",
            ]
        ).to_csv(output_file, index=False)
        return output_file

    if model is None:
        from ultralytics import YOLO

        model = YOLO("yolov8n.pt")

    rows: list[dict[str, Any]] = []
    objects_by_image: dict[str, list[str]] = defaultdict(list)
    conf_by_image: dict[str, list[float]] = defaultdict(list)

    for image_path in paths:
        logger.info("Running YOLO", extra={"channel": image_path.parent.name})
        results = model(str(image_path))
        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue
            for box in boxes:
                class_id = int(box.cls[0])
                object_name = model.names[class_id]
                objects_by_image[str(image_path)].append(object_name)
                try:
                    conf_by_image[str(image_path)].append(float(box.conf[0]))
                except (TypeError, IndexError, ValueError):
                    continue
        key = str(image_path)
        rows.append(
            detections_from_results(
                image_path,
                objects_by_image.get(key, []),
                conf_by_image.get(key, []),
            )
        )

    pd.DataFrame(rows).to_csv(output_file, index=False)
    logger.info("Wrote detections CSV", extra={"rows": len(rows)})
    return output_file


if __name__ == "__main__":
    run_yolo_detection()
