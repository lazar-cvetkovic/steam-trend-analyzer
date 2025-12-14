"""
Cluster tag combinations using HDBSCAN
to discover market archetypes and niches.
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np

from sklearn.preprocessing import StandardScaler
import hdbscan

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from backend.app.settings import settings


# -------------------------
# CONFIG
# -------------------------
MIN_CLUSTER_SIZE = 8
MIN_SAMPLES = 5


def main():
    print("=" * 60)
    print("Clustering Tag Combinations (HDBSCAN)")
    print("=" * 60)

    # ------------------------------------------------------------------
    # Load data
    # Pretpostavka: već imaš parquet sa kombinacijama tagova
    # npr: tag_combo_summary.parquet
    # ------------------------------------------------------------------
    path = settings.PROCESSED_DIR / "tag_combo_summary.parquet"
    if not path.exists():
        print("ERROR: tag_combo_summary.parquet not found")
        sys.exit(1)

    df = pd.read_parquet(path)
    print(f"Loaded {len(df)} tag combinations")

    # ------------------------------------------------------------------
    # Feature selection
    # ------------------------------------------------------------------
    features = [
        "risk_ratio",
        "trend_delta",
        "publisher_dependency",
        "weighted_released",
        "weighted_profitable",
        "combo_size",
    ]

    df_feat = df[features].copy()

    # Drop rows with NaN / inf
    df_feat = df_feat.replace([np.inf, -np.inf], np.nan).dropna()

    # Keep alignment
    df = df.loc[df_feat.index].reset_index(drop=True)
    df_feat = df_feat.reset_index(drop=True)

    # ------------------------------------------------------------------
    # Scaling (OBAVEZNO)
    # ------------------------------------------------------------------
    scaler = StandardScaler()
    X = scaler.fit_transform(df_feat)

    # ------------------------------------------------------------------
    # HDBSCAN
    # ------------------------------------------------------------------
    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=MIN_CLUSTER_SIZE,
        min_samples=MIN_SAMPLES,
        metric="euclidean",
        cluster_selection_method="eom"
    )

    labels = clusterer.fit_predict(X)
    df["cluster"] = labels

    # ------------------------------------------------------------------
    # Basic stats
    # ------------------------------------------------------------------
    n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
    noise_ratio = (labels == -1).mean()

    print(f"Clusters found: {n_clusters}")
    print(f"Noise ratio: {noise_ratio:.2%}")

    # ------------------------------------------------------------------
    # Cluster summary
    # ------------------------------------------------------------------
    summary = (
        df[df["cluster"] != -1]
        .groupby("cluster")
        .agg(
            combos=("tag_combo", "count"),
            avg_risk=("risk_ratio", "mean"),
            avg_trend=("trend_delta", "mean"),
            avg_publisher_dep=("publisher_dependency", "mean"),
            avg_combo_size=("combo_size", "mean"),
        )
        .sort_values("avg_risk")
    )

    print("\nCluster overview:")
    print(summary)

    # ------------------------------------------------------------------
    # Save results
    # ------------------------------------------------------------------
    out_path = settings.PROCESSED_DIR / "tag_combo_clusters.parquet"
    df.to_parquet(out_path, index=False)

    print(f"\n[OK] Saved clustered data to {out_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
