import hashlib
import random
from typing import List, Tuple

def _seed_from_inputs(*parts: str) -> int:
    h = hashlib.sha256(("|".join(parts)).encode("utf-8")).hexdigest()
    return int(h[:8], 16)

def mock_predict_tags(
    preferred_genres: List[str],
    all_known_tags: List[str],
    team_size: int,
    commercial_games_built_count: int,
    art_heavy_level: int,
    max_dev_months: int,
    revenue_expected_k: int,
    top_n: int = 10
) -> List[Tuple[str, float]]:
    """
    Returns list of (tag, probability) where probabilities sum to 1.0 (approximately).
    Deterministic for same inputs.
    """
    archetypes = load_market_archetypes()

    preferred = {t.lower().strip() for t in preferred_genres if t}

    scored = []

    for arch in archetypes:
        score = 0.0

        score += max(0.0, 5.0 - arch["avg_risk"])

        score += arch["avg_trend"] * 2.0

        if team_size <= 3 and arch["avg_combo_size"] > 2:
            score -= 1.0

        if art_heavy_level >= 7:
            score -= arch["avg_combo_size"] * 0.5

        if commercial_games_built_count == 0:
            score -= arch["avg_publisher_dependency"] * 2.0

        for combo in arch["top_tag_combinations"]:
            tags = combo["tags"].split(",")
            if any(t.strip().lower() in preferred for t in tags):
                score += 1.5

        scored.append((arch, score))

    scored.sort(key=lambda x: x[1], reverse=True)

    results = []
    for arch, s in scored:
        for combo in arch["top_tag_combinations"]:
            results.append((combo["tags"], float(s)))
            if len(results) >= top_n:
                break
        if len(results) >= top_n:
            break

    total = sum(v for _, v in results) or 1.0
    return [(t, v / total) for t, v in results]
