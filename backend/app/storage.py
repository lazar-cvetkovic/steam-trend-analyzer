"""Data storage layer with caching."""
import json
from pathlib import Path
from typing import Dict, Optional, List
import pandas as pd
from .settings import settings


# Module-level cache
_tag_summary_cache: Optional[pd.DataFrame] = None
_tag_month_stats_cache: Optional[pd.DataFrame] = None
_tag_complexity_cache: Optional[Dict[str, int]] = None
_games_cache: Optional[pd.DataFrame] = None
_market_archetypes_cache: Optional[list[dict]] = None
_combo_clusters_cache: Optional[pd.DataFrame] = None

def load_tag_combo_clusters() -> pd.DataFrame:
    """
    Load clustered tag combinations (HDBSCAN output) with in-memory caching.
    """
    global _combo_clusters_cache

    path = settings.PROCESSED_DIR / "tag_combo_clusters.parquet"

    if _combo_clusters_cache is None:
        if not path.exists():
            raise FileNotFoundError(
                f"Tag combo clusters not found at {path}. "
                "Run:\n"
                "  python scripts/build_tag_combo_summary.py\n"
                "  python scripts/cluster_tag_combinations.py"
            )
        _combo_clusters_cache = pd.read_parquet(path)

    return _combo_clusters_cache.copy()

def load_market_archetypes() -> list[dict]:
    global _market_archetypes_cache
    path = settings.PROCESSED_DIR / "market_archetypes.json"
    if _market_archetypes_cache is None:
        if not path.exists():
            raise FileNotFoundError("market_archetypes.json not found")
        with open(path, "r", encoding="utf-8") as f:
            _market_archetypes_cache = json.load(f)
    return _market_archetypes_cache

def load_tag_summary() -> pd.DataFrame:
    """Load tag summary parquet file with caching."""
    global _tag_summary_cache
    if _tag_summary_cache is None:
        if not settings.TAG_SUMMARY_PARQUET.exists():
            raise FileNotFoundError(
                f"Tag summary not found at {settings.TAG_SUMMARY_PARQUET}. "
                "Run scripts/build_all.py first."
            )
        _tag_summary_cache = pd.read_parquet(settings.TAG_SUMMARY_PARQUET)
    return _tag_summary_cache.copy()


def load_tag_month_stats() -> pd.DataFrame:
    """Load tag month stats parquet file with caching."""
    global _tag_month_stats_cache
    if _tag_month_stats_cache is None:
        if not settings.TAG_MONTH_STATS_PARQUET.exists():
            raise FileNotFoundError(
                f"Tag month stats not found at {settings.TAG_MONTH_STATS_PARQUET}. "
                "Run scripts/build_all.py first."
            )
        _tag_month_stats_cache = pd.read_parquet(settings.TAG_MONTH_STATS_PARQUET)
    return _tag_month_stats_cache.copy()


def load_tag_complexity() -> Dict[str, int]:
    """Load tag complexity mapping from JSON with caching."""
    global _tag_complexity_cache
    if _tag_complexity_cache is None:
        if not settings.TAG_COMPLEXITY_JSON.exists():
            raise FileNotFoundError(
                f"Tag complexity config not found at {settings.TAG_COMPLEXITY_JSON}"
            )
        with open(settings.TAG_COMPLEXITY_JSON, "r", encoding="utf-8") as f:
            _tag_complexity_cache = json.load(f)
    return _tag_complexity_cache.copy()


def clear_cache():
    """Clear all caches (useful for testing or reloading data)."""
    global _tag_summary_cache, _tag_month_stats_cache, _tag_complexity_cache
    _tag_summary_cache = None
    _tag_month_stats_cache = None
    _tag_complexity_cache = None


def load_games() -> pd.DataFrame:
    """Load games parquet file with caching."""
    global _games_cache
    if _games_cache is None:
        if not settings.GAMES_PARQUET.exists():
            raise FileNotFoundError(
                f"Games parquet not found at {settings.GAMES_PARQUET}. "
                "Run scripts/build_all.py first."
            )
        _games_cache = pd.read_parquet(settings.GAMES_PARQUET)
    return _games_cache.copy()
