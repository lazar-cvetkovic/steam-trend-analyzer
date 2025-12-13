"""Application settings and path configuration."""
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings with file paths."""
    
    # Project root (parent of backend/)
    PROJECT_ROOT: Path = Path(__file__).parent.parent.parent
    
    # Data paths
    RAW_CSV: Path = PROJECT_ROOT / "data" / "raw" / "steam_games.csv"
    PROCESSED_DIR: Path = PROJECT_ROOT / "data" / "processed"
    GAMES_PARQUET: Path = PROCESSED_DIR / "games.parquet"
    TAG_MONTH_STATS_PARQUET: Path = PROCESSED_DIR / "tag_month_stats.parquet"
    TAG_SUMMARY_PARQUET: Path = PROCESSED_DIR / "tag_summary.parquet"
    
    # Config paths
    CONFIG_DIR: Path = PROJECT_ROOT / "data" / "config"
    TAG_COMPLEXITY_JSON: Path = CONFIG_DIR / "tag_complexity.json"
    
    # Recommender weights
    W_SUCCESS: float = 1.0
    W_TREND: float = 0.7
    W_SATURATION: float = 0.15
    DEFAULT_COMPLEXITY: int = 3
    
    class Config:
        case_sensitive = True


settings = Settings()

