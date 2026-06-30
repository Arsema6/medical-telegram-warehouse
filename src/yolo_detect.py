from ultralytics import YOLO
from pathlib import Path
from collections import defaultdict
import pandas as pd

# =========================
# 1. Load YOLO model
# =========================
model = YOLO("yolov8n.pt")

# =========================
# 2. Paths
# =========================
IMAGE_DIR = Path("data/raw/images")
OUTPUT_DIR = Path("data/processed")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# =========================
# 3. Product-like objects
# =========================
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
    "laptop"
}

# =========================
# 4. Classification function
# =========================
def classify_image(objects):
    objects = set(objects)

    has_person = "person" in objects
    has_product = len(objects.intersection(PRODUCT_OBJECTS)) > 0

    if has_person and has_product:
        return "promotional"

    if has_person and not has_product:
        return "lifestyle"

    if has_product and not has_person:
        return "product_display"

    return "other"


# =========================
# 5. Scan images and run YOLO
# =========================
image_objects = defaultdict(list)

image_extensions = [".jpg", ".jpeg", ".png"]

print("Starting YOLO detection...")

for image_path in IMAGE_DIR.rglob("*"):

    if image_path.suffix.lower() not in image_extensions:
        continue

    print(f"Processing: {image_path}")

    results = model(str(image_path))

    for result in results:
        boxes = result.boxes

        if boxes is None:
            continue

        for box in boxes:
            class_id = int(box.cls[0])
            object_name = model.names[class_id]

            image_objects[str(image_path)].append(object_name)


# =========================
# 6. Build final dataset
# =========================
final_data = []

for image_path, objects in image_objects.items():

    category = classify_image(objects)

    # Extract metadata
    path_obj = Path(image_path)

    final_data.append({
        "image_path": image_path,
        "channel_name": path_obj.parent.name,
        "message_id": path_obj.stem,
        "detected_objects": list(set(objects)),
        "image_category": category
    })


# =========================
# 7. Save CSV
# =========================
df = pd.DataFrame(final_data)

output_file = OUTPUT_DIR / "image_detections.csv"
df.to_csv(output_file, index=False)

print("\nDONE ✅")
print(f"Total images processed: {len(df)}")
print(f"Saved to: {output_file}")