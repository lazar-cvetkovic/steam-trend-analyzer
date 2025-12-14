"""
Analyze clustered tag combinations
and extract actionable market archetypes.
"""
import json
import sys
from pathlib import Path
import pandas as pd

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from backend.app.settings import settings


# -------------------------
# CONFIG
# -------------------------
MIN_COMBOS = 15
MAX_AVG_RISK = 4.0
MAX_PUBLISHER_DEP = 0.65
MIN_TREND = 0.0
TOP_COMBOS_PER_CLUSTER = 10


def main():
    print("=" * 60)
    print("Analyzing Market Clusters")
    print("=" * 60)

    path = settings.PROCESSED_DIR / "tag_combo_clusters.parquet"
    if not path.exists():
        print("ERROR: tag_combo_clusters.parquet not found")
        sys.exit(1)

    df = pd.read_parquet(path)
    print(f"Loaded {len(df)} clustered tag combinations")

    # ---------------------------------------------------------
    # Aggregate cluster-level stats
    # ---------------------------------------------------------
    cluster_stats = (
        df[df["cluster"] != -1]
        .groupby("cluster")
        .agg(
            combos=("tag_combo", "count"),
            avg_risk=("risk_ratio", "mean"),
            avg_trend=("trend_delta", "mean"),
            avg_publisher_dep=("publisher_dependency", "mean"),
            avg_combo_size=("combo_size", "mean"),
        )
    )

    # ---------------------------------------------------------
    # Filter "actionable" clusters
    # ---------------------------------------------------------
    candidates = cluster_stats[
        (cluster_stats["combos"] >= MIN_COMBOS) &
        (cluster_stats["avg_risk"] <= MAX_AVG_RISK) &
        (cluster_stats["avg_trend"] >= MIN_TREND) &
        (cluster_stats["avg_publisher_dep"] <= MAX_PUBLISHER_DEP)
    ].sort_values("avg_risk")

    print("\n=== Candidate Market Archetypes ===")
    print(candidates)

    # ---------------------------------------------------------
    # Drill-down per cluster
    # ---------------------------------------------------------
    for cluster_id in candidates.index:
        print("\n" + "-" * 60)
        print(f"CLUSTER {cluster_id}")
        print(cluster_stats.loc[cluster_id])

        top = (
            df[df["cluster"] == cluster_id]
            .sort_values("risk_ratio")
            .head(TOP_COMBOS_PER_CLUSTER)
        )

        print("\nTop tag combinations:")
        for _, row in top.iterrows():
            print(
                f"  {row['tag_combo']} "
                f"(risk={row['risk_ratio']:.2f}, trend={row['trend_delta']:.2f})"
            )

    print("\n" + "=" * 60)
    print("Cluster analysis complete")

    # ---------------------------------------------------------
    # EXPORT MARKET ARCHETYPES (FINAL ML INPUT)
    # ---------------------------------------------------------
    archetypes = []

    for cluster_id in candidates.index:
        cluster_row = cluster_stats.loc[cluster_id]

        top_combos = (
            df[df["cluster"] == cluster_id]
            .sort_values("risk_ratio")
            .head(TOP_COMBOS_PER_CLUSTER)
        )

        archetypes.append({
            "cluster_id": int(cluster_id),
            "combos_count": int(cluster_row["combos"]),
            "avg_risk": float(cluster_row["avg_risk"]),
            "avg_trend": float(cluster_row["avg_trend"]),
            "avg_publisher_dependency": float(cluster_row["avg_publisher_dep"]),
            "avg_combo_size": float(cluster_row["avg_combo_size"]),
            "top_tag_combinations": [
                {
                    "tags": row["tag_combo"],
                    "risk": float(row["risk_ratio"]),
                    "trend": float(row["trend_delta"])
                }
                for _, row in top_combos.iterrows()
            ]
        })

    out_path = settings.PROCESSED_DIR / "market_archetypes.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(archetypes, f, indent=2)

    print(f"\n[OK] Saved market archetypes to {out_path}")

if __name__ == "__main__":
    main()
