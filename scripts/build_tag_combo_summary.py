"""
Build tag COMBINATION risk summary
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import date
from itertools import combinations
from collections import defaultdict

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from backend.app.settings import settings

# -------------------------
# CONFIG (SAFE)
# -------------------------
TIME_DECAY_K = 0.2
RECENT_MONTHS = 24

MAX_TAGS_PER_GAME = 6        # <<< KLJUČNO
MAX_COMBO_SIZE = 2           # <<< KLJUČNO
MIN_GAMES_WEIGHT = 8

PRINT_EVERY = 5000


def compute_time_weight(release_date):
    if pd.isna(release_date):
        return np.nan
    age_years = (date.today() - release_date).days / 365.25
    return np.exp(-TIME_DECAY_K * age_years)


def main():
    print("=" * 60)
    print("SAFE Tag Combo Summary")
    print("=" * 60)

    df = pd.read_parquet(settings.GAMES_PARQUET)
    print(f"Loaded {len(df)} games")

    df["time_weight"] = df["release_date_parsed"].apply(compute_time_weight)
    df["time_weight"] = df["time_weight"].fillna(df["time_weight"].median())
    df["is_profitable"] = (df["total_reviews"] >= 100).astype(int)

    df["has_publisher"] = (
        df["publishers"].notna()
        & df["developers"].notna()
        & (df["publishers"] != df["developers"])
    ).astype(int)

    cutoff_recent = pd.Timestamp.today().normalize() - pd.DateOffset(months=RECENT_MONTHS)

    # INCREMENTAL AGGREGATION (NO HUGE DF)
    agg = defaultdict(lambda: {
        "released_w": 0.0,
        "profitable_w": 0.0,
        "recent_released_w": 0.0,
        "recent_profitable_w": 0.0,
        "pub_prof": 0,
        "nopub_prof": 0,
    })

    try:
        for idx, row in df.iterrows():
            if idx % PRINT_EVERY == 0 and idx > 0:
                print(f"Processed {idx}/{len(df)} games")

            tags = row.get("tags_parsed")
            if tags is None:
                continue

            if isinstance(tags, np.ndarray):
                tags = tags.tolist()

            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split(",") if t.strip()]

            if not isinstance(tags, (list, tuple)) or len(tags) == 0:
                continue

            tags = list(dict.fromkeys(t.lower().strip() for t in tags if t))[:MAX_TAGS_PER_GAME]

            is_recent = (
                pd.notna(row["release_date_parsed"])
                and pd.Timestamp(row["release_date_parsed"]) >= cutoff_recent
            )

            for k in range(1, min(len(tags), MAX_COMBO_SIZE) + 1):
                for combo in combinations(tags, k):
                    key = ",".join(combo)
                    a = agg[key]

                    w = row["time_weight"]
                    p = row["is_profitable"]

                    a["released_w"] += w
                    a["profitable_w"] += w * p

                    if is_recent:
                        a["recent_released_w"] += w
                        a["recent_profitable_w"] += w * p

                    if row["has_publisher"]:
                        a["pub_prof"] += p
                    else:
                        a["nopub_prof"] += p

    except KeyboardInterrupt:
        print("\n[INTERRUPTED] Gracefully stopping…")

    # BUILD FINAL DF
    rows = []
    for combo, a in agg.items():
        if a["released_w"] < MIN_GAMES_WEIGHT:
            continue

        risk = a["released_w"] / max(a["profitable_w"], 1e-6)

        recent_ratio = a["recent_released_w"] / max(a["recent_profitable_w"], 1e-6) if a["recent_released_w"] else risk
        old_ratio = (a["released_w"] - a["recent_released_w"]) / max(
            (a["profitable_w"] - a["recent_profitable_w"]), 1e-6
        )

        trend = recent_ratio - old_ratio
        trend = max(min(trend, 5.0), -5.0)

        pub_dep = a["pub_prof"] / max(a["pub_prof"] + a["nopub_prof"], 1)

        rows.append({
            "tag_combo": combo,
            "combo_size": combo.count(",") + 1,
            "weighted_released": round(a["released_w"], 3),
            "weighted_profitable": round(a["profitable_w"], 3),
            "risk_ratio": round(risk, 3),
            "trend_delta": round(trend, 3),
            "publisher_dependency": round(pub_dep, 3),
        })

    out = pd.DataFrame(rows).sort_values("risk_ratio")
    out_path = settings.PROCESSED_DIR / "tag_combo_summary.parquet"
    out.to_parquet(out_path, index=False)

    print(f"[OK] Saved {len(out)} combos")
    print(out.head(10)[["tag_combo", "risk_ratio"]])
    print("=" * 60)


if __name__ == "__main__":
    main()
