"""Ingest Steam games CSV and convert to normalized Parquet format."""
import sys
from pathlib import Path
import pandas as pd
from dateutil import parser as date_parser

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from backend.app.settings import settings


def parse_tags(tags_str: str) -> list:
    """
    Parse tags string robustly.
    
    Handles:
    - JSON arrays: ["Tag1", "Tag2"]
    - Comma-separated: "Tag1, Tag2, Tag3"
    - Empty/missing values
    """
    if pd.isna(tags_str) or tags_str == "":
        return []
    
    tags_str = str(tags_str).strip()
    
    # Try JSON parsing if it looks like JSON
    if tags_str.startswith("["):
        try:
            import json
            tags = json.loads(tags_str)
            if isinstance(tags, list):
                return [str(t).strip() for t in tags if t]
            return []
        except (json.JSONDecodeError, ValueError):
            pass
    
    # Fall back to comma splitting
    tags = [t.strip() for t in tags_str.split(",") if t.strip()]
    return tags


def parse_release_date(date_str):
    """Parse release date with error handling."""
    if pd.isna(date_str) or date_str == "":
        return None
    
    date_str = str(date_str).strip()
    
    try:
        # Try parsing with dateutil
        parsed = date_parser.parse(date_str, fuzzy=True)
        return parsed.date()
    except (ValueError, TypeError, OverflowError):
        return None


def coerce_int(value, default=0):
    """Coerce value to int with default."""
    if pd.isna(value):
        return default
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return default


def main():
    """Main ingestion function."""
    print("=" * 60)
    print("Steam Games CSV Ingestion")
    print("=" * 60)
    
    # Validate input
    if not settings.RAW_CSV.exists():
        print(f"ERROR: Input CSV not found at {settings.RAW_CSV}")
        print("Please place steam_games.csv in data/raw/")
        sys.exit(1)
    
    print(f"Reading CSV from {settings.RAW_CSV}...")
    df = pd.read_csv(settings.RAW_CSV, low_memory=False)
    print(f"Loaded {len(df)} rows")
    
    # Create output directory
    settings.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    
    # Normalize data types
    print("Normalizing data types...")
    
    # Parse release_date
    print("  - Parsing release_date...")
    df["release_date_parsed"] = df["release_date"].apply(parse_release_date)
    
    # Parse tags
    print("  - Parsing tags...")
    df["tags_parsed"] = df["tags"].apply(parse_tags)
    
    # Coerce total_reviews
    print("  - Coercing total_reviews...")
    df["total_reviews"] = df["total_reviews"].apply(lambda x: coerce_int(x, 0))
    
    # Compute success flag
    print("  - Computing success flag...")
    df["success"] = (df["total_reviews"] >= 100).astype(int)
    
    # Select and rename columns for output
    output_columns = [
        "name", "steam_appid", "required_age", "controller_support",
        "supported_languages", "developers", "publishers", "platforms",
        "categories", "genres", "release_date", "release_date_parsed",
        "followers", "estimated_wishlists", "tags", "tags_parsed",
        "price", "estimated_revenue", "currency", "owners",
        "average_forever", "average_2weeks", "median_forever", "median_2weeks",
        "concurrent_users", "total_positive", "total_negative",
        "total_reviews", "success"
    ]
    
    # Only include columns that exist
    available_columns = [col for col in output_columns if col in df.columns]
    df_output = df[available_columns].copy()
    
    # Save to parquet
    print(f"Writing to {settings.GAMES_PARQUET}...")
    df_output.to_parquet(settings.GAMES_PARQUET, index=False, engine="pyarrow")
    print(f"[OK] Saved {len(df_output)} rows to {settings.GAMES_PARQUET}")
    print("=" * 60)
    print("Ingestion complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()

