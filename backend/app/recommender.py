"""Tag recommendation scoring logic."""
import math
from typing import Optional
import pandas as pd
from .settings import settings
from .storage import load_tag_summary, load_tag_complexity


def compute_complexity_penalty(team_size: int, complexity_score: int) -> float:
    """
    Compute complexity penalty based on team size and tag complexity.
    
    Args:
        team_size: Number of team members
        complexity_score: Complexity score of the tag (1-5)
    
    Returns:
        Penalty value to subtract from score
    """
    if team_size <= 1:
        return 0.35 * max(0, complexity_score - 2)
    elif 2 <= team_size <= 3:
        return 0.22 * max(0, complexity_score - 3)
    elif 4 <= team_size <= 5:
        return 0.12 * max(0, complexity_score - 4)
    else:  # team_size >= 6
        return 0.0


def compute_score(
    recent_success_rate_24m: float,
    trend_score: float,
    released_last_6m: int,
    complexity_penalty: float,
    prefer_bonus: float = 0.0
) -> float:
    """
    Compute recommendation score for a tag.
    
    Args:
        recent_success_rate_24m: Average success rate over last 24 months
        trend_score: Trend score (recent - previous)
        released_last_6m: Number of games released in last 6 months
        complexity_penalty: Penalty for complexity vs team size
        prefer_bonus: Bonus for preferred tags
    
    Returns:
        Final recommendation score
    """
    saturation_penalty = settings.W_SATURATION * math.log(1 + released_last_6m)
    
    score = (
        settings.W_SUCCESS * recent_success_rate_24m
        + settings.W_TREND * trend_score
        - saturation_penalty
        - complexity_penalty
        + prefer_bonus
    )
    
    return score


def generate_reasons(
    recent_success_rate_24m: float,
    trend_score: float,
    released_last_6m: int,
    complexity_penalty: float,
    team_size: int,
    complexity_score: int
) -> list[str]:
    """
    Generate human-readable reasons for the recommendation score.
    
    Args:
        recent_success_rate_24m: Average success rate over last 24 months
        trend_score: Trend score
        released_last_6m: Number of games released in last 6 months
        complexity_penalty: Penalty applied
        team_size: Team size
        complexity_score: Tag complexity score
    
    Returns:
        List of reason strings
    """
    reasons = []
    
    if recent_success_rate_24m >= 0.3:
        reasons.append("High recent success rate")
    elif recent_success_rate_24m >= 0.15:
        reasons.append("Moderate recent success rate")
    else:
        reasons.append("Low recent success rate")
    
    if trend_score > 0.1:
        reasons.append("Strong positive trend")
    elif trend_score > 0.0:
        reasons.append("Positive trend")
    elif trend_score < -0.1:
        reasons.append("Negative trend")
    
    if released_last_6m >= 50:
        reasons.append("High saturation (many recent releases)")
    elif released_last_6m >= 20:
        reasons.append("Moderate saturation")
    else:
        reasons.append("Low saturation")
    
    if complexity_penalty > 0:
        reasons.append(f"Penalized for small team (size {team_size}) vs high complexity (score {complexity_score})")
    elif complexity_score >= 4 and team_size < 6:
        reasons.append("Moderate complexity for team size")
    else:
        reasons.append("Good complexity match for team size")
    
    return reasons


def recommend_tags(
    team_size: int,
    top_n: int = 10,
    prefer_tags: Optional[list[str]] = None,
    avoid_tags: Optional[list[str]] = None,
    allow_tags: Optional[list[str]] = None
) -> tuple[list[dict], dict]:
    """
    Recommend tags based on scoring model.
    
    Args:
        team_size: Number of team members
        top_n: Number of recommendations to return
        prefer_tags: Tags to add bonus to (case-insensitive)
        avoid_tags: Tags to exclude (case-insensitive)
        allow_tags: Only consider these tags (case-insensitive)
    
    Returns:
        Tuple of (recommendations list, metadata dict)
    """
    prefer_tags = prefer_tags or []
    avoid_tags = avoid_tags or []
    
    # Normalize tag lists to lowercase for comparison
    prefer_tags_lower = [t.lower().strip() for t in prefer_tags]
    avoid_tags_lower = [t.lower().strip() for t in avoid_tags]
    allow_tags_lower = None
    if allow_tags:
        allow_tags_lower = [t.lower().strip() for t in allow_tags]
    
    # Load data
    tag_summary = load_tag_summary()
    complexity_map = load_tag_complexity()
    
    # Filter by allow_tags if specified
    if allow_tags_lower:
        tag_summary = tag_summary[
            tag_summary["tag"].str.lower().str.strip().isin(allow_tags_lower)
        ]
    
    # Filter out avoid_tags
    if avoid_tags_lower:
        tag_summary = tag_summary[
            ~tag_summary["tag"].str.lower().str.strip().isin(avoid_tags_lower)
        ]
    
    if len(tag_summary) == 0:
        return [], {"data_last_month": "", "unique_tags": 0}
    
    # Compute scores
    recommendations = []
    for _, row in tag_summary.iterrows():
        tag = str(row["tag"]).strip()
        tag_lower = tag.lower()
        
        complexity_score = complexity_map.get(tag, settings.DEFAULT_COMPLEXITY)
        complexity_penalty = compute_complexity_penalty(team_size, complexity_score)
        
        prefer_bonus = 0.05 if tag_lower in prefer_tags_lower else 0.0
        
        score = compute_score(
            recent_success_rate_24m=float(row["recent_success_rate_24m"]),
            trend_score=float(row["trend_score"]),
            released_last_6m=int(row["released_last_6m"]),
            complexity_penalty=complexity_penalty,
            prefer_bonus=prefer_bonus
        )
        
        reasons = generate_reasons(
            recent_success_rate_24m=float(row["recent_success_rate_24m"]),
            trend_score=float(row["trend_score"]),
            released_last_6m=int(row["released_last_6m"]),
            complexity_penalty=complexity_penalty,
            team_size=team_size,
            complexity_score=complexity_score
        )
        
        recommendations.append({
            "tag": tag,
            "score": round(score, 4),
            "recent_success_rate_24m": round(float(row["recent_success_rate_24m"]), 4),
            "trend_score": round(float(row["trend_score"]), 4),
            "released_last_6m": int(row["released_last_6m"]),
            "complexity_score": complexity_score,
            "complexity_penalty": round(complexity_penalty, 4),
            "reasons": reasons
        })
    
    # Sort by score descending
    recommendations.sort(key=lambda x: x["score"], reverse=True)
    
    # Get top_n
    top_recommendations = recommendations[:top_n]
    
    # Get metadata
    last_month = str(tag_summary["last_month"].max()) if "last_month" in tag_summary.columns else ""
    unique_tags = len(tag_summary)
    
    meta = {
        "data_last_month": last_month,
        "unique_tags": unique_tags
    }
    
    return top_recommendations, meta

