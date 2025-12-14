"""
Build tag COMBINATION risk summary based on profitability,
time decay, trend, and publisher dependency.

Outputs TOP 5 lowest-risk tag combinations.
"""

import sys
from pathlib import Path
from datetime import date
from itertools import combinations

import pandas as pd
import numpy as np

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from backend.app.settings import settings


# =========================
# CONFIG
# =========================
TIME_DECAY_K = 0.2
RECENT_MONTHS = 24

MIN_GAMES = 30          # minimal number of games supporting a combo
MAX_COMBO_SIZE = 3      # 1, 2 or 3 tag combinations
TOP_K = 50               # final output size


# =========================
# WHITELIST / BLACKLIST
# =========================
WHITELIST = {
    # --- genres / mechanics ---
    "action","action-adventure","action roguelike","action rpg","action rts",
    "adventure","arcade","arena shooter","auto battler","base building",
    "battle royale","beat 'em up","boomer shooter","boss rush","bullet hell",
    "card battler","card game","casual","character action game","city builder",
    "clicker","colony sim","combat racing","crpg","dating sim","deckbuilding",
    "dungeon crawler","escape room","extraction shooter","fighting",
    "first-person","farming","farming sim","flight","fps","god game",
    "grand strategy","hack and slash","hidden object","hobby sim","horror",
    "idler","immersive sim","interactive fiction","jrpg","life sim",
    "looter shooter","management","match 3","medical sim","metroidvania",
    "mmorpg","moba","mystery dungeon","on-rails shooter","open world",
    "open world survival craft","otome","outbreak sim","party game",
    "party-based rpg","platformer","point & click","political sim",
    "precision platformer","puzzle","puzzle platformer","racing",
    "real time tactics","real-time with pause","rhythm","roguelike",
    "roguelike deckbuilder","roguelite","roguevania","rpg","rts","runner",
    "sandbox","shoot 'em up","shooter","side scroller","simulation",
    "social deduction","sokoban","souls-like","space sim","spectacle fighter",
    "sports","stealth","strategy","strategy rpg","survival","survival horror",
    "tactical","tactical rpg","third-person shooter","tower defense",
    "trading card game","traditional roguelike","turn-based",
    "turn-based strategy","turn-based tactics","twin stick shooter",
    "visual novel","walking simulator","wargame","word game",
    "2d platformer","3d platformer",

    # --- themes / secondary ---
    "aliens","anime","archery","automation","automobile sim","baseball",
    "basketball","bmx","bowling","boxing","choose your own adventure",
    "cooking","creature collector","driving","dwarf","fishing",
    "football (american)","football (soccer)","gambling","golf",
    "job simulator","mahjong","mini golf","mining","motocross","motorbike",
    "parkour","pirates","programming","resource management","sailing",
    "shop keeper","skateboarding","skating","skiing","snowboarding",
    "spaceships","tabletop","tanks","tennis","time management"
}

BLACKLIST = {
    # meta / noise / presentation / platform / vibes
    "2d","3d","abstract","atmospheric","cartoon","cartoony","cinematic",
    "cozy","cute","dark","educational","early access","family friendly",
    "free to play","indie","multiplayer","singleplayer","pixel graphics",
    "procedural generation","realistic","retro","stylized","vr",
    "violent","war","zombies"
}


# =========================
# HELPERS
# =========================
def compute_time_weight(release_date):
    if pd.isna(release_date):
        return np.nan
    age_years = (date.today() - release_date).days / 365.25
    return np.exp(-TIME_DECAY_K * age_years)


def normalize_tags(raw_tags):
    if raw_tags is None:
        return []

    if hasattr(raw_tags, "tolist"):
        raw_tags = raw_tags.tolist()

    if not isinstance(raw_tags, (list, tuple)):
        return []

    out = []
    for t in raw_tags:
        t = str(t).strip().lower()
        if t in WHITELIST and t not in BLACKLIST:
            out.append(t)
    return sorted(set(out))


# =========================
# MAIN
# =========================
def main():
    print("=" * 60)
    print("Building TAG COMBINATION Risk Summary")
    print("=" * 60)

    df = pd.read_parquet(settings.GAMES_PARQUET)
    print(f"Loaded {len(df)} games")

    # --- time weight ---
    df["time_weight"] = df["release_date_parsed"].apply(compute_time_weight)
    df["time_weight"] = df["time_weight"].fillna(df["time_weight"].median())

    # --- profitability ---
    df["is_profitable"] = (df["total_reviews"] >= 100).astype(int)

    # --- normalize tags ---
    df["tags_norm"] = df["tags_parsed"].apply(normalize_tags)

    # --- generate combinations per game ---
    combo_rows = []

    for _, row in df.iterrows():
        tags = row["tags_norm"]
        if len(tags) == 0:
            continue

        for k in range(1, min(MAX_COMBO_SIZE, len(tags)) + 1):
            for combo in combinations(tags, k):
                combo_rows.append({
                    "combo": combo,
                    "time_weight": row["time_weight"],
                    "is_profitable": row["is_profitable"],
                    "release_date": row["release_date_parsed"]
                })

    combo_df = pd.DataFrame(combo_rows)
    print(f"Generated {len(combo_df)} combo rows")

    # --- recency ---
    cutoff = pd.Timestamp.today().normalize() - pd.DateOffset(months=RECENT_MONTHS)
    combo_df["release_date"] = pd.to_datetime(combo_df["release_date"])
    combo_df["is_recent"] = combo_df["release_date"] >= cutoff

    # --- aggregate ---
    results = []

    for combo, g in combo_df.groupby("combo"):
        games = g["time_weight"].sum()
        if games < MIN_GAMES:
            continue

        profitable = (g["time_weight"] * g["is_profitable"]).sum()
        risk_ratio = games / max(profitable, 1e-6)

        results.append({
            "tags": ", ".join(combo),
            "combo_size": len(combo),
            "weighted_released": round(games, 2),
            "weighted_profitable": round(profitable, 2),
            "risk_ratio": round(risk_ratio, 3)
        })

    out = (
        pd.DataFrame(results)
        .sort_values("risk_ratio", ascending=True)
        .head(TOP_K)
    )

    # --- save ---
    out_path = settings.PROCESSED_DIR / "tag_combo_risk_summary.parquet"
    out.to_parquet(out_path, index=False)

    print("\nTOP 5 LOWEST-RISK TAG COMBINATIONS:")
    print(out)
    print("=" * 60)


if __name__ == "__main__":
    main()
