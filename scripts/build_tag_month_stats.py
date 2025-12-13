"""Build tag month statistics from games data."""
import sys
from pathlib import Path
import pandas as pd

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from backend.app.settings import settings


def main():
    """Build tag month statistics."""
    print("=" * 60)
    print("Building Tag Month Statistics")
    print("=" * 60)
    
    # Validate input
    if not settings.GAMES_PARQUET.exists():
        print(f"ERROR: Games parquet not found at {settings.GAMES_PARQUET}")
        print("Please run scripts/ingest_csv_to_parquet.py first")
        sys.exit(1)
    
    print(f"Reading games data from {settings.GAMES_PARQUET}...")
    df = pd.read_parquet(settings.GAMES_PARQUET)
    print(f"Loaded {len(df)} games")
    
    # Filter out games without release_date_parsed
    df = df[df["release_date_parsed"].notna()].copy()
    print(f"Games with valid release dates: {len(df)}")
    
    # Extract year-month
    df["year_month"] = pd.to_datetime(df["release_date_parsed"]).dt.to_period("M").astype(str)
    
    # Explode tags_parsed to one row per tag
    print("Exploding tags...")
    tag_rows = []
    for _, row in df.iterrows():
        tags = row.get("tags_parsed", [])
        # Handle both lists and numpy arrays
        if tags is None or (hasattr(tags, '__len__') and len(tags) == 0):
            continue
        # Convert to list if it's a numpy array
        if hasattr(tags, 'tolist'):
            tags = tags.tolist()
        elif not isinstance(tags, (list, tuple)):
            continue
        for tag in tags:
            if tag and str(tag).strip():
                tag_rows.append({
                    "tag": str(tag).strip(),
                    "year_month": row["year_month"],
                    "success": row.get("success", 0)
                })
    
    if not tag_rows:
        print("ERROR: No tags found in data")
        sys.exit(1)
    
    df_tags = pd.DataFrame(tag_rows)
    print(f"Generated {len(df_tags)} tag-game-month records")
    
    # Aggregate by tag and year_month
    print("Aggregating statistics...")
    stats = df_tags.groupby(["tag", "year_month"]).agg(
        released_count=("tag", "count"),
        success_count=("success", "sum")
    ).reset_index()
    
    # Compute success_rate
    stats["success_rate"] = stats["success_count"] / stats["released_count"]
    
    # Sort by tag and year_month
    stats = stats.sort_values(["tag", "year_month"])
    
    # Save to parquet
    print(f"Writing to {settings.TAG_MONTH_STATS_PARQUET}...")
    settings.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    stats.to_parquet(settings.TAG_MONTH_STATS_PARQUET, index=False, engine="pyarrow")
    print(f"[OK] Saved {len(stats)} tag-month records")
    print(f"  Unique tags: {stats['tag'].nunique()}")
    print(f"  Date range: {stats['year_month'].min()} to {stats['year_month'].max()}")
    print("=" * 60)
    print("Tag month statistics complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()

