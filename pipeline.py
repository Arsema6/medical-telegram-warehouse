"""Dagster job wiring extract, load, transform, and optional YOLO enrichment."""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

from dagster import In, Nothing, Out, job, op

from src.config import PROJECT_ROOT, get_settings
from src.load_image_detection import load_detections
from src.load_to_postgres import load_raw_messages
from src.logging_utils import configure_logging
from src.scraper import run_scrape
from src.yolo_detect import run_yolo_detection

logger = logging.getLogger(__name__)


def _configure() -> None:
    configure_logging(get_settings().log_level)


@op(out=Out(Nothing))
def scrape_telegram_data() -> None:
    _configure()
    logger.info("Starting Telegram scrape", extra={"op": "scrape"})
    run_scrape()


@op(ins={"start": In(Nothing)}, out=Out(Nothing))
def load_raw_to_postgres() -> None:
    _configure()
    rows = load_raw_messages()
    logger.info("Loaded raw messages", extra={"op": "load_raw", "rows": rows})


@op(ins={"start": In(Nothing)}, out=Out(Nothing))
def run_dbt_transformations() -> None:
    _configure()
    project = PROJECT_ROOT / "medical_warehouse"
    result = subprocess.run(
        [
            "dbt",
            "run",
            "--project-dir",
            str(project),
            "--profiles-dir",
            str(project),
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(PROJECT_ROOT),
    )
    if result.returncode != 0:
        raise RuntimeError(f"dbt run failed: {result.stderr or result.stdout}")
    logger.info("dbt run completed", extra={"op": "dbt"})


@op(ins={"start": In(Nothing)})
def run_yolo_enrichment() -> None:
    _configure()
    settings = get_settings()
    if settings.skip_yolo:
        logger.info("SKIP_YOLO is set; loading detections CSV if present", extra={"op": "yolo"})
        load_detections(settings)
        return
    run_yolo_detection(settings)
    load_detections(settings)


@job
def etl_pipeline():
    loaded = load_raw_to_postgres(start=scrape_telegram_data())
    transformed = run_dbt_transformations(start=loaded)
    run_yolo_enrichment(start=transformed)


@op(out=Out(Nothing))
def seed_demo_data() -> None:
    """Demo path that does not call Telegram."""
    from scripts.seed_demo import seed_demo

    _configure()
    seed_demo()


@job
def demo_pipeline():
    transformed = run_dbt_transformations(start=seed_demo_data())
    run_yolo_enrichment(start=transformed)


if __name__ == "__main__":
    print("Run `dagster dev -f pipeline.py` from the repo root.")
    print(f"Python: {sys.executable} cwd={Path.cwd()}")
