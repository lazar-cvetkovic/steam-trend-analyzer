from __future__ import annotations

from collections import Counter
from datetime import date
from typing import List, Tuple

import pandas as pd

def _month_str(dt: pd.Timestamp) -> str:
    return dt.to_period("M").astype(str)

def compute_genres_trend_data(
    games: pd.DataFrame,
    start: date,
    end: date,
    profitability_type: str,
    min_number_for_profitability: int
) -> tuple[list[dict], list[dict], list[dict], int, int]:
    df = games.copy()
    if "release_date_parsed" not in df.columns:
        return [], [], [], 0, 0

    df = df[df["release_date_parsed"].notna()].copy()
    df["release_dt"] = pd.to_datetime(df["release_date_parsed"])
    df = df[(df["release_dt"].dt.date >= start) & (df["release_dt"].dt.date <= end)].copy()
    if len(df) == 0:
        return [], [], [], 0, 0

    df["year_month"] = df["release_dt"].dt.to_period("M").astype(str)

    released = df.groupby("year_month").size().rename("released_count").reset_index()

    pt = profitability_type.lower().strip()
    if pt == "wishlists":
        metric_col = "estimated_wishlists"
    elif pt == "reviews":
        metric_col = "total_reviews"
    else:
        metric_col = "estimated_revenue"

    if metric_col not in df.columns:
        df[metric_col] = 0

    metric = pd.to_numeric(df[metric_col], errors="coerce").fillna(0).astype(int)
    df["_metric"] = metric
    df["_profitable"] = (df["_metric"] >= int(min_number_for_profitability)).astype(int)

    prof = df.groupby("year_month")["_profitable"].sum().rename("profitable_count").reset_index()

    merged = pd.merge(released, prof, on="year_month", how="left").fillna(0)
    merged["profitable_count"] = merged["profitable_count"].astype(int)
    merged["ratio"] = merged["profitable_count"] / merged["released_count"]

    released_points = [{"date": str(r["year_month"]), "y": int(r["released_count"])} for _, r in merged.iterrows()]
    profitable_points = [{"date": str(r["year_month"]), "y": int(r["profitable_count"])} for _, r in merged.iterrows()]
    ratio_points = [{"date": str(r["year_month"]), "y": float(r["ratio"])} for _, r in merged.iterrows()]

    total_released = int(merged["released_count"].sum())
    total_profitable = int(merged["profitable_count"].sum())

    return released_points, profitable_points, ratio_points, total_released, total_profitable

def _contains_ci(hay: str, needle: str) -> bool:
    return needle.lower() in (hay or "").lower()

def compute_deep_data(
    games: pd.DataFrame,
    tags: List[str],
    wishlist_min: int,
    wishlist_max: int,
    revenue_min: int,
    revenue_max: int,
    reviews_min: int,
    reviews_max: int,
    start: date,
    end: date
) -> dict:
    df = games.copy()

    if "release_date_parsed" in df.columns:
        df = df[df["release_date_parsed"].notna()].copy()
        df["release_dt"] = pd.to_datetime(df["release_date_parsed"])
        df = df[(df["release_dt"].dt.date >= start) & (df["release_dt"].dt.date <= end)].copy()

    def _to_int(col: str) -> pd.Series:
        if col not in df.columns:
            return pd.Series([0] * len(df))
        return pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

    wish = _to_int("estimated_wishlists")
    rev = _to_int("estimated_revenue")
    reviews = _to_int("total_reviews")
    price = pd.to_numeric(df["price"], errors="coerce").fillna(0.0) if "price" in df.columns else pd.Series([0.0] * len(df))

    df = df[(wish >= wishlist_min) & (wish <= wishlist_max)]
    df = df[(rev >= revenue_min) & (rev <= revenue_max)]
    df = df[(reviews >= reviews_min) & (reviews <= reviews_max)]

    tags_norm = [t.strip().lower() for t in (tags or []) if t and t.strip()]
    if tags_norm and "tags_parsed" in df.columns:
        def has_any_tag(x) -> bool:
            if x is None:
                return False
            if hasattr(x, "tolist"):
                x = x.tolist()
            if not isinstance(x, (list, tuple)):
                return False
            s = {str(v).strip().lower() for v in x if v and str(v).strip()}
            return any(t in s for t in tags_norm)
        df = df[df["tags_parsed"].apply(has_any_tag)]

    if len(df) == 0:
        return {
            "topRevenueGames": [],
            "topWishlistedGames": [],
            "topSupportedLanguages": [],
            "percentThatWentWithPublishers": 0.0,
            "linuxSupportPercentage": 0.0,
            "macSupportPercentage": 0.0,
            "medianPrice": 0.0,
            "averagePrice": 0.0,
            "partialControllerSupportPercentage": 0.0,
            "fullControllerSupportPercentage": 0.0,
            "coopSupportPercentage": 0.0,
            "multiplayerSupportPercentage": 0.0,
            "steamLeaderboardSupportPercentage": 0.0,
            "steamAchievementsSupportPercentage": 0.0
        }

    df["_wish"] = _to_int("estimated_wishlists")
    df["_rev"] = _to_int("estimated_revenue")
    df["_reviews"] = _to_int("total_reviews")
    df["_price"] = price.astype(float)

    top_rev = (
        df.sort_values("_rev", ascending=False)
        .head(20)[["name", "_rev"]]
        .fillna("")
        .to_dict("records")
    )
    top_wish = (
        df.sort_values("_wish", ascending=False)
        .head(20)[["name", "_wish"]]
        .fillna("")
        .to_dict("records")
    )

    # languages
    lang_counter = Counter()
    if "supported_languages" in df.columns:
        for s in df["supported_languages"].fillna("").astype(str).tolist():
            parts = [p.strip() for p in s.replace(";", ",").split(",") if p.strip()]
            for p in parts:
                lang_counter[p] += 1
    top_langs = [k for k, _ in lang_counter.most_common(10)]

    # publisher usage: developers != publishers
    dev = df["developers"].fillna("").astype(str) if "developers" in df.columns else pd.Series([""] * len(df))
    pub = df["publishers"].fillna("").astype(str) if "publishers" in df.columns else pd.Series([""] * len(df))
    has_pub = (dev.str.strip() != "") & (pub.str.strip() != "") & (dev.str.strip() != pub.str.strip())
    percent_with_pub = float(has_pub.mean())

    # platforms
    plat = df["platforms"].fillna("").astype(str) if "platforms" in df.columns else pd.Series([""] * len(df))
    linux_pct = float(plat.apply(lambda x: _contains_ci(x, "linux")).mean())
    mac_pct = float(plat.apply(lambda x: _contains_ci(x, "mac")).mean())

    # categories flags
    cat = df["categories"].fillna("").astype(str) if "categories" in df.columns else pd.Series([""] * len(df))

    partial_controller = float(cat.apply(lambda x: _contains_ci(x, "Partial Controller Support")).mean())
    full_controller = float(cat.apply(lambda x: _contains_ci(x, "Full controller support")).mean())
    coop = float(cat.apply(lambda x: _contains_ci(x, "Co-op")).mean())
    multiplayer = float(cat.apply(lambda x: _contains_ci(x, "Multi-player")).mean())
    leaderboards = float(cat.apply(lambda x: _contains_ci(x, "Leaderboards")).mean())
    achievements = float(cat.apply(lambda x: _contains_ci(x, "Achievements")).mean())

    median_price = float(df["_price"].median())
    avg_price = float(df["_price"].mean())

    return {
        "topRevenueGames": [{"name": r["name"], "value": int(r["_rev"])} for r in top_rev],
        "topWishlistedGames": [{"name": r["name"], "value": int(r["_wish"])} for r in top_wish],
        "topSupportedLanguages": top_langs,
        "percentThatWentWithPublishers": percent_with_pub,
        "linuxSupportPercentage": linux_pct,
        "macSupportPercentage": mac_pct,
        "medianPrice": median_price,
        "averagePrice": avg_price,
        "partialControllerSupportPercentage": partial_controller,
        "fullControllerSupportPercentage": full_controller,
        "coopSupportPercentage": coop,
        "multiplayerSupportPercentage": multiplayer,
        "steamLeaderboardSupportPercentage": leaderboards,
        "steamAchievementsSupportPercentage": achievements
    }
