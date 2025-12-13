# Repository Architecture & Testing Guide

## 🏗️ Architecture Overview

**Important: This project does NOT use a traditional database!**

Instead, it uses **Parquet files** (columnar storage format) for data persistence. This is a file-based, serverless approach perfect for MVPs.

### Data Storage Architecture

```
┌─────────────────┐
│  CSV Input      │  data/raw/steam_games.csv
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Data Pipeline  │  scripts/*.py
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  Parquet Files (Processed Data)     │
├─────────────────────────────────────┤
│  • games.parquet                    │  ← Normalized game data
│  • tag_month_stats.parquet          │  ← Monthly tag statistics
│  • tag_summary.parquet              │  ← Precomputed summaries
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────┐
│  FastAPI App    │  backend/app/main.py
│  (In-Memory     │  Loads Parquet → Pandas DataFrames
│   Caching)      │  Caches in memory for fast access
└─────────────────┘
```

## 📊 Data Flow

### Step 1: Data Ingestion (`scripts/ingest_csv_to_parquet.py`)

**Input:** `data/raw/steam_games.csv` (your Steam games data)

**Process:**
1. Reads CSV with Pandas
2. Parses tags (handles JSON arrays `["Tag1", "Tag2"]` or comma-separated `"Tag1, Tag2"`)
3. Parses release dates (handles various formats gracefully)
4. Computes `success` flag: `1` if `total_reviews >= 100`, else `0`
5. Normalizes data types

**Output:** `data/processed/games.parquet`

**Example transformation:**
```python
# Input CSV row:
{
  "name": "Game X",
  "tags": "Roguelike, Indie, Action",  # or ["Roguelike", "Indie"]
  "release_date": "2023-01-15",
  "total_reviews": 150
}

# Output Parquet row:
{
  "name": "Game X",
  "tags_parsed": ["Roguelike", "Indie", "Action"],  # List
  "release_date_parsed": date(2023, 1, 15),  # Date object
  "success": 1  # Computed
}
```

### Step 2: Tag Month Statistics (`scripts/build_tag_month_stats.py`)

**Input:** `data/processed/games.parquet`

**Process:**
1. Groups games by tag and year-month
2. Counts how many games were released per tag per month
3. Counts how many were successful (success = 1)
4. Computes success rate: `success_count / released_count`

**Output:** `data/processed/tag_month_stats.parquet`

**Example output:**
```python
{
  "tag": "Roguelike",
  "year_month": "2023-01",
  "released_count": 12,
  "success_count": 3,
  "success_rate": 0.25  # 3/12 = 25% success rate
}
```

### Step 3: Tag Summary (`scripts/build_tag_summary.py`)

**Input:** `data/processed/tag_month_stats.parquet`

**Process:**
1. For each tag, computes:
   - `recent_success_rate_24m`: Average success rate over last 24 months
   - `released_last_6m`: Total games released in last 6 months
   - `trend_score`: `avg(success_rate last 6m) - avg(success_rate previous 12m)`
   - `last_month`: Most recent month this tag appeared

**Output:** `data/processed/tag_summary.parquet`

**Example output:**
```python
{
  "tag": "Roguelike",
  "recent_success_rate_24m": 0.28,  # 28% success over 24 months
  "released_last_6m": 15,           # 15 games in last 6 months
  "trend_score": 0.12,               # Improving trend (+12%)
  "last_month": "2024-01"
}
```

## 🚀 How the API Works

### Storage Layer (`backend/app/storage.py`)

**Key Feature: In-Memory Caching**

When the API starts, it loads Parquet files into memory as Pandas DataFrames. Subsequent requests use cached data (no disk I/O).

```python
# First request: Loads from disk
tag_summary = load_tag_summary()  # Reads Parquet → DataFrame → Cache

# Subsequent requests: Uses cache
tag_summary = load_tag_summary()  # Returns cached DataFrame (fast!)
```

**Cache is module-level:** Data persists across API requests until server restart.

### Recommender Logic (`backend/app/recommender.py`)

**Scoring Formula:**
```python
score = (1.0 × recent_success_rate_24m)      # Success weight
      + (0.7 × trend_score)                   # Trend weight
      - (0.15 × log(1 + released_last_6m))    # Saturation penalty
      - complexity_penalty(team_size, complexity)  # Team size penalty
      + (0.05 if tag in prefer_tags)          # Preference bonus
```

**Complexity Penalty:**
- Solo dev (≤1): Penalty for complexity > 2
- Small team (2-3): Penalty for complexity > 3
- Medium team (4-5): Penalty for complexity > 4
- Large team (≥6): No penalty

**Example:**
```python
# Tag: "MMO" (complexity=5), Team size: 2
complexity_penalty = 0.22 × max(0, 5-3) = 0.44  # High penalty!

# Tag: "Puzzle" (complexity=2), Team size: 2
complexity_penalty = 0.22 × max(0, 2-3) = 0.0   # No penalty
```

## 🧪 How to Test

### 1. Unit Tests (Scoring Logic)

```bash
# Run all tests
pytest tests/

# Run with verbose output
pytest tests/ -v

# Run specific test file
pytest tests/test_recommender.py
```

**What's tested:**
- Complexity penalty calculations for different team sizes
- Score computation with various inputs
- Reason generation logic

### 2. Manual API Testing

#### Option A: Using curl

```bash
# Health check
curl http://localhost:8000/health

# Get recommendations
curl -X POST http://localhost:8000/recommend \
  -H "Content-Type: application/json" \
  -d '{
    "team_size": 2,
    "top_n": 5,
    "prefer_tags": ["Indie"],
    "avoid_tags": ["MMO"]
  }'

# Get tag timeseries
curl http://localhost:8000/tag/Roguelike/timeseries

# Get all tags
curl http://localhost:8000/tags
```

#### Option B: Using Swagger UI (Recommended)

1. Start the API: `uvicorn backend.app.main:app --reload --port 8000`
2. Open browser: http://localhost:8000/docs
3. Click "Try it out" on any endpoint
4. Fill in request body and click "Execute"

#### Option C: Using Python requests

```python
import requests

# Health check
response = requests.get("http://localhost:8000/health")
print(response.json())  # {"ok": true}

# Get recommendations
response = requests.post(
    "http://localhost:8000/recommend",
    json={
        "team_size": 2,
        "top_n": 10,
        "prefer_tags": ["Indie", "Roguelike"],
        "avoid_tags": ["MMO"]
    }
)
print(response.json())
```

### 3. End-to-End Testing

**Full workflow test:**

```bash
# 1. Ensure CSV is in place
ls data/raw/steam_games.csv

# 2. Build all data files
python scripts/build_all.py

# 3. Verify Parquet files were created
ls data/processed/
# Should see: games.parquet, tag_month_stats.parquet, tag_summary.parquet

# 4. Start API
uvicorn backend.app.main:app --reload --port 8000

# 5. Test endpoints (use Swagger UI or curl)
```

### 4. Testing Data Processing Scripts

```bash
# Test individual scripts
python scripts/ingest_csv_to_parquet.py
python scripts/build_tag_month_stats.py
python scripts/build_tag_summary.py

# Or test all at once
python scripts/build_all.py
```

**Check outputs:**
```python
import pandas as pd

# Check games data
df = pd.read_parquet("data/processed/games.parquet")
print(df.head())
print(f"Total games: {len(df)}")

# Check tag stats
df_stats = pd.read_parquet("data/processed/tag_month_stats.parquet")
print(df_stats.head())
print(f"Unique tags: {df_stats['tag'].nunique()}")

# Check tag summary
df_summary = pd.read_parquet("data/processed/tag_summary.parquet")
print(df_summary.head())
```

## 🔍 Key Components Explained

### `backend/app/settings.py`
- Centralized configuration
- Defines all file paths
- Contains scoring weights

### `backend/app/storage.py`
- Data loading functions
- Module-level caching (loads once, reuses)
- Error handling for missing files

### `backend/app/recommender.py`
- Core scoring algorithm
- Complexity penalty logic
- Reason generation

### `backend/app/schemas.py`
- Pydantic models for request/response validation
- Type safety and automatic API documentation

### `backend/app/main.py`
- FastAPI application
- Route handlers
- Error handling

## 🐛 Common Issues & Debugging

### Issue: "Data not found" error

**Cause:** Parquet files don't exist

**Solution:**
```bash
python scripts/build_all.py
```

### Issue: API returns empty recommendations

**Possible causes:**
1. No tags match your filters (`allow_tags` too restrictive)
2. All tags are in `avoid_tags`
3. Data hasn't been built yet

**Debug:**
```python
# Check tag summary
import pandas as pd
df = pd.read_parquet("data/processed/tag_summary.parquet")
print(df.head(20))
print(f"Total tags: {len(df)}")
```

### Issue: Cache not updating after data rebuild

**Solution:** Restart the API server (cache is in-memory)

### Issue: Port already in use

**Solution:**
```bash
uvicorn backend.app.main:app --reload --port 8001
```

## 📈 Performance Characteristics

- **Data Loading:** ~1-2 seconds on first request (reads Parquet)
- **Subsequent Requests:** <10ms (uses cache)
- **Recommendation Calculation:** ~50-100ms for 1000+ tags
- **Memory Usage:** ~50-200MB depending on dataset size

## 🔄 Data Refresh Workflow

When you get new CSV data:

```bash
# 1. Replace CSV
cp new_steam_games.csv data/raw/steam_games.csv

# 2. Rebuild data
python scripts/build_all.py

# 3. Restart API (to clear cache)
# Stop current server (Ctrl+C)
uvicorn backend.app.main:app --reload --port 8000
```

## 🎯 Summary

- **No Database:** Uses Parquet files (file-based storage)
- **In-Memory Caching:** Fast API responses after first load
- **Precomputed Stats:** Tag summaries computed offline for speed
- **Deterministic:** Same inputs = same outputs
- **Robust:** Handles missing data gracefully

The system is designed for **read-heavy workloads** with **infrequent data updates**. Perfect for an MVP!

