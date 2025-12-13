"""FastAPI application main module."""
from datetime import datetime
from fastapi import FastAPI, HTTPException, Path as PathParam
import pandas as pd

from .schemas import (
    HealthResponse,
    RecommendationInput,
    RecommendationResponse,
    RecommendationItem,
    RecommendationMeta,
    TagTimeseriesResponse,
    TimeseriesPoint,
    TagsListResponse
)
from .recommender import recommend_tags
from .storage import load_tag_summary, load_tag_month_stats


app = FastAPI(
    title="Steam Tag Recommender API",
    description="API for recommending Steam game tags based on success, trends, and complexity",
    version="1.0.0"
)


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint."""
    return HealthResponse(ok=True)


@app.post("/recommend", response_model=RecommendationResponse)
async def recommend(inputs: RecommendationInput):
    """
    Get tag recommendations based on team size and preferences.
    """
    try:
        recommendations, meta = recommend_tags(
            team_size=inputs.team_size,
            top_n=inputs.top_n,
            prefer_tags=inputs.prefer_tags,
            avoid_tags=inputs.avoid_tags,
            allow_tags=inputs.allow_tags
        )
        
        recommendation_items = [RecommendationItem(**r) for r in recommendations]
        
        return RecommendationResponse(
            generated_at=datetime.utcnow(),
            inputs=inputs,
            recommendations=recommendation_items,
            meta=RecommendationMeta(**meta)
        )
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Data not found. Please run scripts/build_all.py first. Error: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@app.get("/tag/{tag}/timeseries", response_model=TagTimeseriesResponse)
async def get_tag_timeseries(tag: str = PathParam(..., description="Tag name")):
    """
    Get timeseries data for a specific tag.
    """
    try:
        tag_stats = load_tag_month_stats()
        
        # Filter by tag (case-insensitive)
        tag_filtered = tag_stats[
            tag_stats["tag"].str.lower().str.strip() == tag.lower().strip()
        ]
        
        if len(tag_filtered) == 0:
            raise HTTPException(
                status_code=404,
                detail=f"Tag '{tag}' not found in data"
            )
        
        # Sort by year_month
        tag_filtered = tag_filtered.sort_values("year_month")
        
        points = [
            TimeseriesPoint(
                year_month=str(row["year_month"]),
                released_count=int(row["released_count"]),
                success_rate=round(float(row["success_rate"]), 4)
            )
            for _, row in tag_filtered.iterrows()
        ]
        
        return TagTimeseriesResponse(
            tag=tag,
            points=points
        )
    except HTTPException:
        raise
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Data not found. Please run scripts/build_all.py first. Error: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@app.get("/tags", response_model=TagsListResponse)
async def get_tags():
    """
    Get list of all available tags.
    """
    try:
        tag_summary = load_tag_summary()
        tags = sorted(tag_summary["tag"].astype(str).str.strip().unique().tolist())
        return TagsListResponse(tags=tags)
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Data not found. Please run scripts/build_all.py first. Error: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

