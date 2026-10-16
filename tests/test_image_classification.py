from pathlib import Path

from src.image_classification import classify_image
from src.yolo_detect import detections_from_results


def test_classify_promotional() -> None:
    assert classify_image(["person", "bottle"]) == "promotional"


def test_classify_lifestyle() -> None:
    assert classify_image(["person"]) == "lifestyle"


def test_classify_product_display() -> None:
    assert classify_image(["bottle", "box"]) == "product_display"


def test_classify_other() -> None:
    assert classify_image(["chair"]) == "other"


def test_classify_is_case_insensitive() -> None:
    assert classify_image(["Person", "BOTTLE"]) == "promotional"


def test_detections_from_results_extracts_channel_and_message() -> None:
    row = detections_from_results(Path("data/raw/images/chemed/101.jpg"), ["bottle"], [0.9])
    assert row["channel_name"] == "chemed"
    assert row["message_id"] == "101"
    assert row["image_category"] == "product_display"
    assert row["max_confidence"] == 0.9
