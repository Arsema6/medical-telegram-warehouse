import subprocess
import sys
from dagster import job, op

# -------------------------
# OP 1
# -------------------------
@op
def scrape_telegram_data():
    print("Scraping Telegram data...")
    result = subprocess.run([sys.executable, "src/scraper.py"], capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"Scraper failed: {result.stderr}")
    print("Scraping completed successfully")
    return "raw_data"

# -------------------------
# OP 2
# -------------------------
@op
def load_raw_to_postgres(data):
    print("Loading into Postgres...")
    result = subprocess.run([sys.executable, "src/load_to_postgres.py"], capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"Load to Postgres failed: {result.stderr}")
    print("Load to Postgres completed successfully")
    return "loaded"

# -------------------------
# OP 3
# -------------------------
@op
def run_dbt_transformations(data):
    print("Running dbt transformations...")
    result = subprocess.run(["dbt", "run"], capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"dbt run failed: {result.stderr}")
    print("dbt transformations completed successfully")
    return "dbt_done"

# -------------------------
# OP 4
# -------------------------
@op
def run_yolo_enrichment(data):
    print("Running YOLO detection...")
    result = subprocess.run([sys.executable, "src/yolo_detect.py"], capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"YOLO detection failed: {result.stderr}")
    print("YOLO detection completed successfully")
    
    # Load detection results to Postgres
    print("Loading detection results to Postgres...")
    result = subprocess.run([sys.executable, "src/load_image_detection.py"], capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"Load detection results failed: {result.stderr}")
    print("Detection results loaded successfully")
    
    return "yolo_done"

# -------------------------
# JOB
# -------------------------
@job
def etl_pipeline():
    data = scrape_telegram_data()
    loaded = load_raw_to_postgres(data)
    dbt = run_dbt_transformations(loaded)
    run_yolo_enrichment(dbt)