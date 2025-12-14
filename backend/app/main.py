"""FastAPI application main module."""
import json
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
    DeepDataInput, DeepDataOutput,
    ClusterListResponse,
    ClusterDetailResponse,
    ClusterSummary,
    TagComboItem
)
from .recommender import recommend_tags
from .storage import load_tag_summary, load_tag_month_stats, load_games, load_tag_combo_clusters
from .ml_mock import mock_predict_tags
from .llm_service import generate_trend_structured_response
from .response_store import save_trend_response, get_trend_response
from .analytics import compute_genres_trend_data, compute_deep_data
from .settings import settings

app = FastAPI(
    title="Steam Tag Recommender API",
    description="API for recommending Steam game tags based on success, trends, and complexity",
    version="1.0.0"
)

print(f"[LLM] model={settings.PERPLEXITY_MODEL!r} key_set={bool(settings.PERPLEXITY_API_KEY.strip())}")


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
        async def _process_trend():
            # -------------------------------------------------
            # 1) LOAD BASE DATA (THREAD POOL)
            # -------------------------------------------------
            tag_summary = await asyncio.to_thread(load_tag_summary)
            all_tags = sorted(tag_summary["tag"].astype(str).str.strip().unique().tolist())

            games = await asyncio.to_thread(load_games)
            combo_clusters = await asyncio.to_thread(load_tag_combo_clusters)

            # -------------------------------------------------
            # 2) ML PREDICTION (FAST)
            # -------------------------------------------------
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

            primary_tag = ml_top[0][0] if ml_top else (preferredGenres[0] if preferredGenres else "Indie")

            # -------------------------------------------------
            # 3) ENRICH ML WITH CLUSTER STATS
            # -------------------------------------------------
            combo_map = {}
            if "tag_combo" in combo_clusters.columns:
                for _, row in combo_clusters.iterrows():
                    key = str(row.get("tag_combo", "")).strip().lower()
                    if key:
                        combo_map[key] = {
                            "risk_ratio": float(row.get("risk_ratio", 0.0)),
                            "trend_delta": float(row.get("trend_delta", 0.0)),
                            "publisher_dependency": float(row.get("publisher_dependency", 0.0)),
                            "combo_size": int(row.get("combo_size", 0)),
                            "weighted_released": float(row.get("weighted_released", 0.0)),
                            "weighted_profitable": float(row.get("weighted_profitable", 0.0)),
                        }

            def _norm_combo(s: str) -> str:
                return ",".join([p.strip().lower() for p in str(s).split(",") if p.strip()])

            ml_enriched = []
            for combo, prob in ml_top:
                k = _norm_combo(combo)
                ml_enriched.append({
                    "combo": combo,
                    "probability": float(prob),
                    "cluster_stats": combo_map.get(k, {})
                })

            # -------------------------------------------------
            # 4) ANALYTICS (PARALLEL)
            # -------------------------------------------------
            today = date.today()
            start = date(2019, 1, 1)

            deep_task = asyncio.to_thread(
                compute_deep_data,
                games=games,
                tags=[primary_tag],
                wishlist_min=0,
                wishlist_max=2_000_000_000,
                revenue_min=0,
                revenue_max=2_000_000_000,
                reviews_min=0,
                reviews_max=2_000_000_000,
                start=start,
                end=today
            )

            trend_task = asyncio.to_thread(
                compute_genres_trend_data,
                games=games,
                start=start,
                end=today,
                profitability_type="wishlists",
                min_number_for_profitability=1000
            )

            deep_data, (
                released_points,
                profitable_points,
                ratio_points,
                total_released,
                total_profitable,
            ) = await asyncio.gather(deep_task, trend_task)

            # -------------------------------------------------
            # 5) BUILD LLM PROMPT
            # -------------------------------------------------
            chat_name = f"Trend • team {teamSize} • {primary_tag}"

            prompt = (
                f"chatName: {chat_name}\n\n"
                f"User constraints:\n"
                f"- teamSize={teamSize}\n"
                f"- preferredGenres={preferredGenres}\n"
                f"- commercialGamesBuiltCount={commercialGamesBuiltCount}\n"
                f"- artHeavyLevel={artHeavyLevel}\n"
                f"- maxDevelopmentTimeInMonths={maxDevelopmentTimeInMonths}\n"
                f"- revenueExpectedInThousandsOfDollars={revenueExpectedInThousandsOfDollars}\n\n"
                f"ML predicted niches (with cluster stats):\n"
                f"{json.dumps(ml_enriched, ensure_ascii=False)}\n\n"
                f"Primary niche deep data:\n"
                f"{json.dumps(deep_data, ensure_ascii=False)}\n\n"
                f"Market trend (last 12 months):\n"
                f"- released={released_points[-12:]}\n"
                f"- profitable={profitable_points[-12:]}\n"
                f"- ratio={ratio_points[-12:]}\n"
                f"- totals: released={total_released}, profitable={total_profitable}\n"
            )

            # -------------------------------------------------
            # 6) LLM → STRUCTURED JSON
            # -------------------------------------------------
            llm = await generate_trend_structured_response(
                prompt=prompt,
                chat_name=chat_name,
                timeout=120
            )

            chat_response_str = json.dumps(llm.chat_response_json, ensure_ascii=False)

            rec = save_trend_response(
                chat_response=chat_response_str,
                action_step_plan=""
            )

            # -------------------------------------------------
            # 7) FINAL RESPONSE (FRONTEND SHAPE)
            # -------------------------------------------------
            return TrendOutput(
                success=True,
                chatName=llm.chat_name,
                chatResponse=chat_response_str,
                responseId=rec.response_id
            )

        return await asyncio.wait_for(_process_trend(), timeout=120.0)

    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Trend computation timed out")

    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=str(e))

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")



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


@app.get("/market-archetypes", response_model=ClusterListResponse)
async def get_market_archetypes(
    min_combos: int = Query(15, ge=1),
    max_avg_risk: float = Query(4.0, ge=0),
    min_trend: float = Query(0.0),
    max_publisher_dep: float = Query(0.65)
):
    df = load_tag_combo_clusters()

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
        .reset_index()
    )

    filtered = summary[
        (summary["combos"] >= min_combos) &
        (summary["avg_risk"] <= max_avg_risk) &
        (summary["avg_trend"] >= min_trend) &
        (summary["avg_publisher_dep"] <= max_publisher_dep)
    ].sort_values("avg_risk")

    return ClusterListResponse(
        clusters=[
            ClusterSummary(
                cluster_id=int(r.cluster),
                combos=int(r.combos),
                avg_risk=float(r.avg_risk),
                avg_trend=float(r.avg_trend),
                avg_publisher_dep=float(r.avg_publisher_dep),
                avg_combo_size=float(r.avg_combo_size),
            )
            for _, r in filtered.iterrows()
        ]
    )

@app.get("/market-archetypes/{cluster_id}", response_model=ClusterDetailResponse)
async def get_market_archetype(cluster_id: int, top_n: int = Query(15, ge=1, le=100)):
    df = load_tag_combo_clusters()

    cluster_df = df[df["cluster"] == cluster_id]
    if cluster_df.empty:
        raise HTTPException(status_code=404, detail="Cluster not found")

    summary = ClusterSummary(
        cluster_id=cluster_id,
        combos=len(cluster_df),
        avg_risk=float(cluster_df["risk_ratio"].mean()),
        avg_trend=float(cluster_df["trend_delta"].mean()),
        avg_publisher_dep=float(cluster_df["publisher_dependency"].mean()),
        avg_combo_size=float(cluster_df["combo_size"].mean()),
    )

    top = (
        cluster_df
        .sort_values("risk_ratio")
        .head(top_n)
    )

    return ClusterDetailResponse(
        cluster=summary,
        top_combinations=[
            TagComboItem(
                tag_combo=row.tag_combo,
                risk_ratio=float(row.risk_ratio),
                trend_delta=float(row.trend_delta),
                publisher_dependency=float(row.publisher_dependency),
                combo_size=int(row.combo_size),
            )
            for _, row in top.iterrows()
        ]
    )
