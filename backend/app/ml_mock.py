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
    base = preferred_genres[:] if preferred_genres else []
    base = [t.strip() for t in base if t and t.strip()]
    base_lower = {t.lower() for t in base}

    candidates = []
    for t in all_known_tags:
        if not t or not str(t).strip():
            continue
        if str(t).strip().lower() in base_lower:
            candidates.append(str(t).strip())

    fallback = [t for t in all_known_tags if str(t).strip().lower() not in base_lower]
    seed = _seed_from_inputs(
        ",".join(sorted(base_lower)),
        str(team_size),
        str(commercial_games_built_count),
        str(art_heavy_level),
        str(max_dev_months),
        str(revenue_expected_k),
    )
    rng = random.Random(seed)
    rng.shuffle(fallback)

    merged = candidates + fallback
    picked = merged[:max(top_n, 10)]

    raw = [rng.random() for _ in picked]
    s = sum(raw) if sum(raw) > 0 else 1.0
    probs = [v / s for v in raw]

    return list(zip(picked[:top_n], probs[:top_n]))
