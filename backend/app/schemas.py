"""Pydantic request/response schemas."""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import date
from enum import Enum

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


class TrendInput(BaseModel):
    teamSize: int = Field(ge=1, le=100)
    preferredGenres: List[str] = Field(default_factory=list)
    commercialGamesBuiltCount: int = Field(ge=0, le=1000)
    artHeavyLevel: int = Field(ge=0, le=10, description="0-10")
    maxDevelopmentTimeInMonths: int = Field(ge=1, le=120)
    revenueExpectedInThousandsOfDollars: int = Field(ge=0, le=100000)

class TrendOutput(BaseModel):
    chat: str
    response_id: int

class ActionStepPlanOutput(BaseModel):
    text: str

class ProfitabilityType(str, Enum):
    wishlists = "wishlists"
    revenue = "revenue"
    reviews = "reviews"  # supported as alias

class GraphPointInt(BaseModel):
    date: str  # "YYYY-MM"
    y: int

class GraphPointFloat(BaseModel):
    date: str
    y: float

class GenresTrendDataOutput(BaseModel):
    released_games: List[GraphPointInt]
    profitable_games: List[GraphPointInt]
    profitability_ratio: List[GraphPointFloat]
    totalNumberOfReleasedGames: int
    totalNumberOfProfitableGames: int

class DeepDataInput(BaseModel):
    tags: List[str] = Field(default_factory=list)
    wishlistMin: int = 0
    wishlistMax: int = 2_000_000_000
    revenueMin: int = 0
    revenueMax: int = 2_000_000_000
    reviewsMin: int = 0
    reviewsMax: int = 2_000_000_000
    startdate: date
    enddate: date

class NamedValueInt(BaseModel):
    name: str
    value: int

class DeepDataOutput(BaseModel):
    topRevenueGames: List[NamedValueInt]
    topWishlistedGames: List[NamedValueInt]
    topSupportedLanguages: List[str]

    percentThatWentWithPublishers: float
    linuxSupportPercentage: float
    macSupportPercentage: float

    medianPrice: float
    averagePrice: float

    partialControllerSupportPercentage: float
    fullControllerSupportPercentage: float
    coopSupportPercentage: float
    multiplayerSupportPercentage: float
    steamLeaderboardSupportPercentage: float
    steamAchievementsSupportPercentage: float


# -------------------------
# CLUSTER / MARKET MODELS
# -------------------------

class TagComboItem(BaseModel):
    tag_combo: str
    risk_ratio: float
    trend_delta: float
    publisher_dependency: float
    combo_size: int


class ClusterSummary(BaseModel):
    cluster_id: int
    combos: int
    avg_risk: float
    avg_trend: float
    avg_publisher_dep: float
    avg_combo_size: float


class ClusterListResponse(BaseModel):
    clusters: list[ClusterSummary]


class ClusterDetailResponse(BaseModel):
    cluster: ClusterSummary
    top_combinations: list[TagComboItem]
