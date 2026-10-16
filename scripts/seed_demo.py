"""Load synthetic public-market demo data (no Telegram credentials)."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from src.config import get_settings
from src.load_image_detection import load_detections
from src.load_to_postgres import load_raw_messages
from src.logging_utils import configure_logging

logger = logging.getLogger(__name__)


def copy_demo_extracts(demo_dir: Path, raw_dir: Path) -> None:
    source = demo_dir / "telegram_messages"
    dest = raw_dir / "telegram_messages"
    if not source.exists():
        raise FileNotFoundError(f"Demo extracts missing: {source}")
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, dest, dirs_exist_ok=True)


def copy_demo_detections(demo_dir: Path, processed_dir: Path) -> Path:
    source = demo_dir / "image_detections.csv"
    processed_dir.mkdir(parents=True, exist_ok=True)
    dest = processed_dir / "image_detections.csv"
    shutil.copyfile(source, dest)
    return dest


def seed_demo() -> dict[str, int]:
    settings = get_settings()
    configure_logging(settings.log_level)
    copy_demo_extracts(settings.demo_data_dir, settings.data_raw_dir)
    detections_csv = copy_demo_detections(settings.demo_data_dir, settings.data_processed_dir)
    messages = load_raw_messages(settings)
    detections = load_detections(settings, detections_csv)
    logger.info("Demo seed complete", extra={"rows": messages})
    return {"messages": messages, "detections": detections}


def main() -> None:
    counts = seed_demo()
    print(f"Seeded demo data: {counts}")


if __name__ == "__main__":
    main()
