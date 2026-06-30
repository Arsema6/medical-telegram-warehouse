# Medical Telegram Warehouse

An end-to-end data pipeline for analyzing Ethiopian medical businesses from public Telegram channels. This project implements a modern ELT architecture using dbt for transformation, Dagster for orchestration, and YOLOv8 for computer vision enrichment.

## Project Overview

This data platform extracts, transforms, and analyzes data from Telegram channels selling medical and pharmaceutical products in Ethiopia. It answers key business questions such as:
- Top 10 most frequently mentioned medical products
- Price and availability variations across channels
- Visual content analysis (images of products vs people)
- Daily and weekly posting trends

## Architecture

```
Telegram Channels → Data Lake (JSON) → PostgreSQL (Raw) → dbt (Transform) → Data Warehouse (Star Schema) → FastAPI
                                    ↓
                              YOLOv8 Detection → Image Analysis
```

### Star Schema Design

**Dimension Tables:**
- `dim_channels`: Channel metadata (name, type, posting statistics)
- `dim_dates`: Time dimension (date, day of week, month, quarter, year, weekend flag)

**Fact Tables:**
- `fct_messages`: Message-level data with foreign keys to dimensions
- `fct_image_detections`: YOLO object detection results integrated with message data

## Project Structure

```
medical-telegram-warehouse/
├── .env                          # Environment variables (API keys, DB credentials)
├── .gitignore
├── docker-compose.yml            # Container orchestration
├── Dockerfile                    # Python environment
├── requirements.txt              # Python dependencies
├── README.md
├── pipeline.py                   # Dagster orchestration
├── data/
│   ├── raw/                      # Data lake
│   │   ├── telegram_messages/    # Scraped JSON files
│   │   └── images/               # Downloaded images
│   └── processed/                # Processed data
├── medical_warehouse/            # dbt project
│   ├── dbt_project.yml
│   ├── profiles.yml              # Database connection config
│   ├── models/
│   │   ├── staging/              # Raw data cleaning
│   │   └── marts/                # Star schema models
│   └── tests/                    # Custom data tests
├── src/
│   ├── scraper.py                # Telegram scraper
│   ├── load_to_postgres.py       # Load raw data to DB
│   ├── yolo_detect.py           # Object detection
│   └── load_image_detection.py   # Load detection results
├── api/                          # FastAPI application
│   ├── main.py
│   ├── database.py
│   └── schemas.py
├── notebooks/                    # Exploratory analysis
├── tests/                        # Unit tests
└── logs/                         # Application logs
```

## Setup Instructions

### Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Telegram API credentials (from my.telegram.org)

### 1. Environment Setup

Create a `.env` file with the following variables:

```env
# Telegram API
API_ID=your_api_id
API_HASH=your_api_hash

# Database
DB_HOST=localhost
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=your_db_password
DB_NAME=medical_warehouse
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Database Setup

Create the PostgreSQL database:

```bash
createdb medical_warehouse
```

### 4. Run the Pipeline

#### Option A: Run with Dagster (Recommended)

```bash
dagster dev -f pipeline.py
```

Access the Dagster UI at http://localhost:3000

#### Option B: Run Individual Scripts

```bash
# Step 1: Scrape Telegram data
python src/scraper.py

# Step 2: Load to PostgreSQL
python src/load_to_postgres.py

# Step 3: Run dbt transformations
cd medical_warehouse
dbt run
dbt test

# Step 4: Run YOLO detection
python src/yolo_detect.py
python src/load_image_detection.py
```

### 5. Start the API

```bash
uvicorn api.main:app --reload
```

Access API documentation at http://localhost:8000/docs

## API Endpoints

### 1. Top Products
Returns the most frequently mentioned terms/products across all channels.

```
GET /api/reports/top-products?limit=10
```

### 2. Channel Activity
Returns posting activity and trends for a specific channel.

```
GET /api/channels/{channel_name}/activity
```

### 3. Message Search
Searches for messages containing a specific keyword.

```
GET /api/search/messages?query=paracetamol&limit=20
```

### 4. Visual Content Stats
Returns statistics about image usage across channels.

```
GET /api/reports/visual-content
```

## Docker Deployment

Build and run with Docker Compose:

```bash
docker-compose up -d
```

This will:
- Start PostgreSQL database
- Build and run the application
- Mount data and logs volumes

## dbt Documentation

Generate and view dbt documentation:

```bash
cd medical_warehouse
dbt docs generate
dbt docs serve
```

Access at http://localhost:8080

## Data Quality Tests

The project includes the following dbt tests:

- **Unique and not null tests** on primary keys
- **Relationship tests** on foreign keys
- **Custom tests:**
  - `assert_no_future_messages.sql`: Ensures no messages have future dates
  - `assert_positive_views.sql`: Ensures view counts are non-negative

Run tests:

```bash
cd medical_warehouse
dbt test
```

## Telegram Channels Scraped

- CheMed Telegram Channel — Medical products
- Lobelia Cosmetics — Cosmetics and health products
- Tikvah Pharma — Pharmaceuticals

## Image Classification

Images are classified using YOLOv8 object detection into:
- **promotional**: Contains person + product
- **product_display**: Contains bottle/container, noPerson
- **lifestyle**: Contains person, no product
- **other**: Neither detected

## Key Technologies

- **Scraping**: Telethon (Telegram API)
- **Database**: PostgreSQL
- **Transformation**: dbt (Data Build Tool)
- **Orchestration**: Dagster
- **Computer Vision**: YOLOv8 (Ultralytics)
- **API**: FastAPI
- **Containerization**: Docker

## Security Considerations

- All credentials are stored in `.env` file (not committed to git)
- Database passwords are loaded from environment variables
- `.gitignore` excludes sensitive files and data

## Future Improvements

- Add more Telegram channels
- Implement fine-tuned YOLO model for medical products
- Add real-time streaming pipeline
- Implement data quality monitoring dashboard
- Add more analytical endpoints

## License

This project is for educational purposes.

## Contact

For questions or issues, please open an issue on GitHub.
