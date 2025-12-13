# Steam Tag Recommender Backend

A FastAPI-based backend for recommending Steam game tags based on success metrics, trends, saturation, and team complexity.

## Features

- **Data Processing**: Ingest Steam games CSV and precompute monthly tag statistics
- **Tag Recommendations**: Score-based recommendations considering:
  - Recent success rate (24 months)
  - Trend analysis (recent vs previous performance)
  - Market saturation (recent releases)
  - Team size vs tag complexity penalty
- **RESTful API**: FastAPI endpoints for recommendations, tag timeseries, and tag lists
- **Deterministic & Robust**: Handles missing data gracefully, deterministic scoring

## Prerequisites

- Python 3.11 or 3.12
- pip (Python package manager)

## Setup

### 1. Create Virtual Environment

**Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

If you get an execution policy error, run:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

**macOS/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r backend/requirements.txt
```

### 3. Prepare Data

Place your `steam_games.csv` file in `data/raw/steam_games.csv`.

The CSV should contain these columns:
- `name`, `steam_appid`, `required_age`, `controller_support`, `supported_languages`
- `developers`, `publishers`, `platforms`, `categories`, `genres`
- `release_date`, `followers`, `estimated_wishlists`, `tags`, `price`
- `estimated_revenue`, `currency`, `owners`
- `average_forever`, `average_2weeks`, `median_forever`, `median_2weeks`
- `concurrent_users`, `total_positive`, `total_negative`, `total_reviews`

### 4. Build Data Files

Run the data processing pipeline:

```bash
python scripts/build_all.py
```

This will:
1. Ingest CSV and convert to Parquet (`data/processed/games.parquet`)
2. Build tag month statistics (`data/processed/tag_month_stats.parquet`)
3. Build tag summary (`data/processed/tag_summary.parquet`)

Alternatively, run scripts individually:
```bash
python scripts/ingest_csv_to_parquet.py
python scripts/build_tag_month_stats.py
python scripts/build_tag_summary.py
```

### 5. Run the API

```bash
uvicorn backend.app.main:app --reload --port 8000
```

The API will be available at:
- API: http://localhost:8000
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## API Endpoints

### GET /health

Health check endpoint.

**Response:**
```json
{
  "ok": true
}
```

**Example:**
```bash
curl http://localhost:8000/health
```

### POST /recommend

Get tag recommendations based on team size and preferences.

**Request Body:**
```json
{
  "team_size": 2,
  "top_n": 10,
  "prefer_tags": ["Indie", "Roguelike"],
  "avoid_tags": ["MMO"],
  "allow_tags": null
}
```

**Response:**
```json
{
  "generated_at": "2024-01-15T10:30:00",
  "inputs": {
    "team_size": 2,
    "top_n": 10,
    "prefer_tags": ["Indie", "Roguelike"],
    "avoid_tags": ["MMO"],
    "allow_tags": null
  },
  "recommendations": [
    {
      "tag": "Roguelike",
      "score": 0.4523,
      "recent_success_rate_24m": 0.28,
      "trend_score": 0.12,
      "released_last_6m": 15,
      "complexity_score": 3,
      "complexity_penalty": 0.0,
      "reasons": [
        "High recent success rate",
        "Positive trend",
        "Low saturation",
        "Good complexity match for team size"
      ]
    }
  ],
  "meta": {
    "data_last_month": "2024-01",
    "unique_tags": 1234
  }
}
```

**Example:**
```bash
curl -X POST http://localhost:8000/recommend \
  -H "Content-Type: application/json" \
  -d '{"team_size": 2, "top_n": 10}'
```

### GET /tag/{tag}/timeseries

Get timeseries data for a specific tag.

**Response:**
```json
{
  "tag": "Roguelike",
  "points": [
    {
      "year_month": "2023-01",
      "released_count": 12,
      "success_rate": 0.18
    },
    {
      "year_month": "2023-02",
      "released_count": 15,
      "success_rate": 0.20
    }
  ]
}
```

**Example:**
```bash
curl http://localhost:8000/tag/Roguelike/timeseries
```

### GET /tags

Get list of all available tags.

**Response:**
```json
{
  "tags": ["Action", "Adventure", "Indie", "RPG", ...]
}
```

**Example:**
```bash
curl http://localhost:8000/tags
```

## Scoring Model

The recommendation score is computed as:

```
score = (w_success * recent_success_rate_24m)
      + (w_trend * trend_score)
      - (w_saturation * log(1 + released_last_6m))
      - (complexity_penalty(team_size, complexity_score))
      + (prefer_bonus if tag in prefer_tags)
```

**Default Weights:**
- `w_success = 1.0`
- `w_trend = 0.7`
- `w_saturation = 0.15`

**Complexity Penalty:**
- Solo (≤1): `0.35 * max(0, complexity - 2)`
- Small (2-3): `0.22 * max(0, complexity - 3)`
- Medium (4-5): `0.12 * max(0, complexity - 4)`
- Large (≥6): `0.0` (no penalty)

**Tag Complexity:** Defined in `data/config/tag_complexity.json` (1-5 scale).

## Project Structure

```
steam-trend-analyzer/
├── backend/
│   └── app/
│       ├── __init__.py
│       ├── main.py          # FastAPI application
│       ├── settings.py       # Configuration and paths
│       ├── schemas.py        # Pydantic models
│       ├── recommender.py    # Scoring logic
│       ├── storage.py        # Data loading with caching
│       └── requirements.txt
├── scripts/
│   ├── ingest_csv_to_parquet.py
│   ├── build_tag_month_stats.py
│   ├── build_tag_summary.py
│   └── build_all.py
├── data/
│   ├── raw/
│   │   └── steam_games.csv
│   ├── processed/            # Generated Parquet files
│   └── config/
│       └── tag_complexity.json
├── tests/
│   └── test_recommender.py
├── README.md
└── .gitignore
```

## Running Tests

```bash
pytest tests/
```

## Common Issues

### Windows PowerShell Execution Policy

If you see an error when activating the virtual environment:
```
cannot be loaded because running scripts is disabled on this system
```

Run:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### VS Code Python Interpreter

If VS Code doesn't detect the virtual environment:
1. Press `Ctrl+Shift+P` (or `Cmd+Shift+P` on macOS)
2. Type "Python: Select Interpreter"
3. Choose the interpreter from `venv/Scripts/python.exe` (Windows) or `venv/bin/python` (macOS/Linux)

### Data Not Found Errors

If you see "Data not found" errors:
1. Ensure `steam_games.csv` is in `data/raw/`
2. Run `python scripts/build_all.py` to generate processed data
3. Check that `data/processed/` contains the Parquet files

### Port Already in Use

If port 8000 is already in use:
```bash
uvicorn backend.app.main:app --reload --port 8001
```

## Development

### Makefile Alternative (Linux/macOS)

Create a `Makefile`:
```makefile
.PHONY: install build run test clean

install:
	pip install -r backend/requirements.txt

build:
	python scripts/build_all.py

run:
	uvicorn backend.app.main:app --reload --port 8000

test:
	pytest tests/

clean:
	rm -rf data/processed/*.parquet
	rm -rf __pycache__ backend/__pycache__ scripts/__pycache__ tests/__pycache__
	rm -rf .pytest_cache
```

Usage:
```bash
make install
make build
make run
```

### PowerShell Commands

For Windows, use these commands:

```powershell
# Install dependencies
pip install -r backend/requirements.txt

# Build data
python scripts/build_all.py

# Run API
uvicorn backend.app.main:app --reload --port 8000

# Run tests
pytest tests/
```

## License

This project is provided as-is for MVP purposes.

