"""Pydantic request/response schemas."""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Health check response."""
    ok: bool


class RecommendationInput(BaseModel):
    """Input for tag recommendation."""
    team_size: int = Field(ge=1, le=100, description="Team size (1-100)")
    top_n: int = Field(default=10, ge=1, le=50, description="Number of recommendations (1-50)")
    prefer_tags: List[str] = Field(default_factory=list, description="Tags to prefer (case-insensitive)")
    avoid_tags: List[str] = Field(default_factory=list, description="Tags to avoid (case-insensitive)")
    allow_tags: Optional[List[str]] = Field(default=None, description="Only consider these tags (case-insensitive)")


class RecommendationItem(BaseModel):
    """Single tag recommendation."""
    tag: str
    score: float
    recent_success_rate_24m: float
    trend_score: float
    released_last_6m: int
    complexity_score: int
    complexity_penalty: float
    reasons: List[str]


class RecommendationMeta(BaseModel):
    """Metadata about recommendations."""
    data_last_month: str
    unique_tags: int


class RecommendationResponse(BaseModel):
    """Response for tag recommendations."""
    generated_at: datetime
    inputs: RecommendationInput
    recommendations: List[RecommendationItem]
    meta: RecommendationMeta


class TimeseriesPoint(BaseModel):
    """Single point in tag timeseries."""
    year_month: str
    released_count: int
    success_rate: float


class TagTimeseriesResponse(BaseModel):
    """Response for tag timeseries."""
    tag: str
    points: List[TimeseriesPoint]


class TagsListResponse(BaseModel):
    """Response for available tags list."""
    tags: List[str]

