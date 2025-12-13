"""Unit tests for recommender scoring functions."""
import pytest
from backend.app.recommender import (
    compute_complexity_penalty,
    compute_score,
    generate_reasons
)


def test_complexity_penalty_solo_team():
    """Test complexity penalty for solo developer."""
    # Solo developer (team_size <= 1)
    assert compute_complexity_penalty(1, 1) == 0.0  # complexity 1, no penalty
    assert compute_complexity_penalty(1, 2) == 0.0  # complexity 2, no penalty
    assert compute_complexity_penalty(1, 3) == 0.35  # complexity 3, penalty = 0.35 * (3-2) = 0.35
    assert compute_complexity_penalty(1, 4) == 0.70  # complexity 4, penalty = 0.35 * (4-2) = 0.70
    assert compute_complexity_penalty(1, 5) == 1.05  # complexity 5, penalty = 0.35 * (5-2) = 1.05


def test_complexity_penalty_small_team():
    """Test complexity penalty for small team (2-3)."""
    # Small team (2-3)
    assert compute_complexity_penalty(2, 1) == 0.0
    assert compute_complexity_penalty(2, 2) == 0.0
    assert compute_complexity_penalty(2, 3) == 0.0  # complexity 3, no penalty
    assert compute_complexity_penalty(2, 4) == 0.22  # complexity 4, penalty = 0.22 * (4-3) = 0.22
    assert compute_complexity_penalty(3, 5) == 0.44  # complexity 5, penalty = 0.22 * (5-3) = 0.44


def test_complexity_penalty_medium_team():
    """Test complexity penalty for medium team (4-5)."""
    # Medium team (4-5)
    assert compute_complexity_penalty(4, 1) == 0.0
    assert compute_complexity_penalty(4, 2) == 0.0
    assert compute_complexity_penalty(4, 3) == 0.0
    assert compute_complexity_penalty(4, 4) == 0.0  # complexity 4, no penalty
    assert compute_complexity_penalty(4, 5) == 0.12  # complexity 5, penalty = 0.12 * (5-4) = 0.12
    assert compute_complexity_penalty(5, 5) == 0.12


def test_complexity_penalty_large_team():
    """Test complexity penalty for large team (6+)."""
    # Large team (6+)
    assert compute_complexity_penalty(6, 5) == 0.0
    assert compute_complexity_penalty(10, 5) == 0.0
    assert compute_complexity_penalty(100, 5) == 0.0


def test_compute_score_basic():
    """Test basic score computation."""
    score = compute_score(
        recent_success_rate_24m=0.3,
        trend_score=0.1,
        released_last_6m=10,
        complexity_penalty=0.0,
        prefer_bonus=0.0
    )
    # score = 1.0 * 0.3 + 0.7 * 0.1 - 0.15 * log(1 + 10) - 0.0
    # log(11) ≈ 2.398
    # score ≈ 0.3 + 0.07 - 0.15 * 2.398 ≈ 0.3 + 0.07 - 0.36 ≈ 0.01
    assert isinstance(score, float)
    assert score > -1.0  # Reasonable range


def test_compute_score_with_penalties():
    """Test score computation with penalties."""
    score_with_penalty = compute_score(
        recent_success_rate_24m=0.3,
        trend_score=0.1,
        released_last_6m=50,
        complexity_penalty=0.5,
        prefer_bonus=0.0
    )
    
    score_no_penalty = compute_score(
        recent_success_rate_24m=0.3,
        trend_score=0.1,
        released_last_6m=10,
        complexity_penalty=0.0,
        prefer_bonus=0.0
    )
    
    # Score with penalty should be lower
    assert score_with_penalty < score_no_penalty


def test_compute_score_with_prefer_bonus():
    """Test score computation with prefer bonus."""
    score_no_bonus = compute_score(
        recent_success_rate_24m=0.3,
        trend_score=0.1,
        released_last_6m=10,
        complexity_penalty=0.0,
        prefer_bonus=0.0
    )
    
    score_with_bonus = compute_score(
        recent_success_rate_24m=0.3,
        trend_score=0.1,
        released_last_6m=10,
        complexity_penalty=0.0,
        prefer_bonus=0.05
    )
    
    # Score with bonus should be higher
    assert score_with_bonus > score_no_bonus
    assert abs(score_with_bonus - score_no_bonus - 0.05) < 0.001


def test_generate_reasons():
    """Test reason generation."""
    reasons = generate_reasons(
        recent_success_rate_24m=0.35,
        trend_score=0.15,
        released_last_6m=5,
        complexity_penalty=0.5,
        team_size=1,
        complexity_score=4
    )
    
    assert isinstance(reasons, list)
    assert len(reasons) > 0
    assert all(isinstance(r, str) for r in reasons)
    
    # Should mention high success rate
    assert any("success" in r.lower() for r in reasons)
    
    # Should mention penalty
    assert any("penal" in r.lower() for r in reasons)


def test_generate_reasons_low_success():
    """Test reason generation for low success rate."""
    reasons = generate_reasons(
        recent_success_rate_24m=0.05,
        trend_score=-0.1,
        released_last_6m=100,
        complexity_penalty=0.0,
        team_size=10,
        complexity_score=2
    )
    
    assert isinstance(reasons, list)
    assert any("low" in r.lower() or "saturation" in r.lower() for r in reasons)

