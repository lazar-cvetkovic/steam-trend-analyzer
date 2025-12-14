"""FastAPI application main module."""
import asyncio
from datetime import datetime, date
from fastapi import FastAPI, HTTPException, Path as PathParam, Query
import pandas as pd

from .schemas import (
    HealthResponse,
    RecommendationInput,
    RecommendationResponse,
    RecommendationItem,
    RecommendationMeta,
    TagTimeseriesResponse,
    TimeseriesPoint,
    TagsListResponse,
    TrendInput, 
    TrendOutput, ActionStepPlanOutput,
    ProfitabilityType, GenresTrendDataOutput,
    DeepDataInput, DeepDataOutput
)
from .recommender import recommend_tags
from .storage import load_tag_summary, load_tag_month_stats, load_tag_summary, load_tag_month_stats, load_games
from .ml_mock import mock_predict_tags
from .llm_service import generate_trend_response
from .response_store import save_trend_response, get_trend_response
from .analytics import compute_genres_trend_data, compute_deep_data

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

@app.get("/trend", response_model=TrendOutput)
async def get_trend(
    teamSize: int = Query(..., ge=1, le=100),
    preferredGenres: list[str] = Query(default_factory=list),
    commercialGamesBuiltCount: int = Query(..., ge=0, le=1000),
    artHeavyLevel: int = Query(..., ge=0, le=10),
    maxDevelopmentTimeInMonths: int = Query(..., ge=1, le=120),
    revenueExpectedInThousandsOfDollars: int = Query(..., ge=0, le=100000),
):
    try:
        tag_summary = load_tag_summary()
        all_tags = sorted(tag_summary["tag"].astype(str).str.strip().unique().tolist())

        ml_top = mock_predict_tags(
            preferred_genres=preferredGenres,
            all_known_tags=all_tags,
            team_size=teamSize,
            commercial_games_built_count=commercialGamesBuiltCount,
            art_heavy_level=artHeavyLevel,
            max_dev_months=maxDevelopmentTimeInMonths,
            revenue_expected_k=revenueExpectedInThousandsOfDollars,
            top_n=10
        )

        primary_tag = ml_top[0][0] if ml_top else (all_tags[0] if all_tags else "Indie")

        games = load_games()

        # Deep data for primary tag (wide filters by default; keep it useful)
        today = date.today()
        default_start = date(2019, 1, 1)
        deep = compute_deep_data(
            games=games,
            tags=[primary_tag],
            wishlist_min=0, wishlist_max=2_000_000_000,
            revenue_min=0, revenue_max=2_000_000_000,
            reviews_min=0, reviews_max=2_000_000_000,
            start=default_start,
            end=today
        )

        # Trend data for primary tag (profitability by wishlists default threshold 1000)
        released_points, profitable_points, ratio_points, total_rel, total_prof = compute_genres_trend_data(
            games=games,
            start=default_start,
            end=today,
            profitability_type="wishlists",
            min_number_for_profitability=1000
        )

        ml_lines = "\n".join([f"- {t}: {p:.3f}" for t, p in ml_top])

        prompt = (
            f"User constraints:\n"
            f"- teamSize={teamSize}\n"
            f"- preferredGenres={preferredGenres}\n"
            f"- commercialGamesBuiltCount={commercialGamesBuiltCount}\n"
            f"- artHeavyLevel={artHeavyLevel}\n"
            f"- maxDevelopmentTimeInMonths={maxDevelopmentTimeInMonths}\n"
            f"- revenueExpectedInThousandsOfDollars={revenueExpectedInThousandsOfDollars}\n\n"
            f"ML predicted tags (mocked):\n{ml_lines}\n\n"
            f"Primary tag chosen for deep dive: {primary_tag}\n\n"
            f"Deep data summary (primary tag slice):\n{deep}\n\n"
            f"Overall market trend stats (all games, wishlists>=1000):\n"
            f"- released_points={released_points[-12:]}\n"
            f"- profitable_points={profitable_points[-12:]}\n"
            f"- ratio_points={ratio_points[-12:]}\n"
            f"- totalReleased={total_rel}, totalProfitable={total_prof}\n"
        )

        # Call LLM with timeout to prevent hanging
        try:
            llm = await asyncio.wait_for(
                generate_trend_response(prompt, timeout=25.0),
                timeout=30.0
            )
        except asyncio.TimeoutError:
            raise HTTPException(
                status_code=504,
                detail="LLM service timeout. Please try again later."
            )
        
        rec = save_trend_response(chat_response=llm.full_text, action_step_plan=llm.action_plan_text)

        return TrendOutput(chat=rec.chat_response, response_id=rec.response_id)

    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=f"Data not found. Run scripts/build_all.py first. Error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/action-step-plan/{response_id}", response_model=ActionStepPlanOutput)
async def get_action_step_plan(response_id: int = PathParam(..., ge=1)):
    rec = get_trend_response(response_id)
    if rec is None:
        raise HTTPException(status_code=404, detail=f"Response id {response_id} not found")
    return ActionStepPlanOutput(text=rec.action_step_plan)


@app.get("/genres-trend-data", response_model=GenresTrendDataOutput)
async def get_genres_trend_data(
    startdate: date = Query(...),
    enddate: date = Query(...),
    profitabilityType: ProfitabilityType = Query(...),
    minNumberForProtifability: int = Query(..., ge=0),
):
    try:
        games = load_games()
        released_points, profitable_points, ratio_points, total_rel, total_prof = compute_genres_trend_data(
            games=games,
            start=startdate,
            end=enddate,
            profitability_type=profitabilityType.value,
            min_number_for_profitability=minNumberForProtifability
        )
        return GenresTrendDataOutput(
            released_games=released_points,
            profitable_games=profitable_points,
            profitability_ratio=ratio_points,
            totalNumberOfReleasedGames=total_rel,
            totalNumberOfProfitableGames=total_prof
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=f"Data not found. Run scripts/build_all.py first. Error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/deep-data", response_model=DeepDataOutput)
async def get_deep_data(
    tags: list[str] = Query(default_factory=list),
    wishlistMin: int = Query(0, ge=0),
    wishlistMax: int = Query(2_000_000_000, ge=0),
    revenueMin: int = Query(0, ge=0),
    revenueMax: int = Query(2_000_000_000, ge=0),
    reviewsMin: int = Query(0, ge=0),
    reviewsMax: int = Query(2_000_000_000, ge=0),
    startdate: date = Query(...),
    enddate: date = Query(...),
):
    try:
        games = load_games()
        out = compute_deep_data(
            games=games,
            tags=tags,
            wishlist_min=wishlistMin,
            wishlist_max=wishlistMax,
            revenue_min=revenueMin,
            revenue_max=revenueMax,
            reviews_min=reviewsMin,
            reviews_max=reviewsMax,
            start=startdate,
            end=enddate
        )
        return DeepDataOutput(**out)
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=f"Data not found. Run scripts/build_all.py first. Error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


