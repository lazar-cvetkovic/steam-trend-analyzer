"""Build tag summary statistics for recommendations."""
import sys
from pathlib import Path
import pandas as pd

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from backend.app.settings import settings


def main():
    """Build tag summary statistics."""
    print("=" * 60)
    print("Building Tag Summary Statistics")
    print("=" * 60)
    
    # Validate input
    if not settings.TAG_MONTH_STATS_PARQUET.exists():
        print(f"ERROR: Tag month stats not found at {settings.TAG_MONTH_STATS_PARQUET}")
        print("Please run scripts/build_tag_month_stats.py first")
        sys.exit(1)
    
    print(f"Reading tag month stats from {settings.TAG_MONTH_STATS_PARQUET}...")
    df = pd.read_parquet(settings.TAG_MONTH_STATS_PARQUET)
    print(f"Loaded {len(df)} tag-month records")
    
    # Ensure year_month is string and sortable
    df["year_month"] = df["year_month"].astype(str)
    
    # Get all unique year_months and sort lexicographically
    all_months = sorted(df["year_month"].unique())
    print(f"Date range: {all_months[0]} to {all_months[-1]}")
    
    # Build summary for each tag
    print("Computing summary statistics...")
    summaries = []
    
    for tag in df["tag"].unique():
        tag_data = df[df["tag"] == tag].sort_values("year_month")
        
        if len(tag_data) == 0:
            continue
        
        # Get last month
        last_month = tag_data["year_month"].max()
        
        # Find last 24 months (where tag appears)
        last_24m_months = sorted(tag_data["year_month"].unique())[-24:]
        last_24m_data = tag_data[tag_data["year_month"].isin(last_24m_months)]
        
        # Recent success rate (last 24 months)
        if len(last_24m_data) > 0:
            recent_success_rate_24m = last_24m_data["success_rate"].mean()
        else:
            recent_success_rate_24m = 0.0
        
        # Last 6 months
        last_6m_months = sorted(tag_data["year_month"].unique())[-6:]
        last_6m_data = tag_data[tag_data["year_month"].isin(last_6m_months)]
        released_last_6m = last_6m_data["released_count"].sum() if len(last_6m_data) > 0 else 0
        
        # Trend score: avg(success_rate last 6m) - avg(success_rate previous 12m)
        if len(last_6m_data) > 0:
            avg_last_6m = last_6m_data["success_rate"].mean()
        else:
            avg_last_6m = 0.0
        
        # Previous 12 months (before last 6)
        all_tag_months = sorted(tag_data["year_month"].unique())
        if len(all_tag_months) > 6:
            prev_12m_months = all_tag_months[-18:-6]  # 12 months before last 6
            prev_12m_data = tag_data[tag_data["year_month"].isin(prev_12m_months)]
            if len(prev_12m_data) > 0:
                avg_prev_12m = prev_12m_data["success_rate"].mean()
            else:
                avg_prev_12m = 0.0
        else:
            avg_prev_12m = 0.0
        
        trend_score = avg_last_6m - avg_prev_12m
        
        summaries.append({
            "tag": tag,
            "recent_success_rate_24m": recent_success_rate_24m,
            "released_last_6m": released_last_6m,
            "trend_score": trend_score,
            "last_month": last_month
        })
    
    df_summary = pd.DataFrame(summaries)
    
    # Save to parquet
    print(f"Writing to {settings.TAG_SUMMARY_PARQUET}...")
    settings.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    df_summary.to_parquet(settings.TAG_SUMMARY_PARQUET, index=False, engine="pyarrow")
    print(f"[OK] Saved {len(df_summary)} tag summaries")
    print("=" * 60)
    print("Tag summary complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()

