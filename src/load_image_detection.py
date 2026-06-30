import os
import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv

load_dotenv()

DB_URL = f"postgresql+psycopg2://{os.getenv('DB_USER', 'postgres')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST', 'localhost')}:{os.getenv('DB_PORT', '5432')}/{os.getenv('DB_NAME', 'medical_warehouse')}"

engine = create_engine(DB_URL)

df = pd.read_csv("data/image_detections.csv")

print("Rows loaded from CSV:", len(df))
print(df.head())

df.to_sql(
    "image_detections",
    engine,
    schema="raw",
    if_exists="append",
    index=False
)

print("✅ Data inserted into raw.image_detections")