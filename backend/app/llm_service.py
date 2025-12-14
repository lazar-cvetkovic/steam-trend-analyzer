from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx

from .settings import settings


@dataclass(frozen=True)
class LlmTrendJsonResult:
    chat_name: str
    chat_response_json: Dict[str, Any]


_SYSTEM_CONTEXT = """
You are an expert Steam market analyst and game producer.

You MUST output STRICT JSON only (no markdown, no commentary, no code fences).

Your job:
Given user constraints + ML predictions + analytics/deep stats + cluster stats,
produce a structured response with EXACTLY this shape:

{
  "chatName": "string",
  "summary": {
    "recommended_niche": "string",
    "core_theme": "string",
    "game_mode": "singleplayer|multiplayer|coop|unknown",
    "recommended_release_window": "string",
    "target_audience": {
      "age_range": { "min": number, "max": number },
      "player_type": "casual|midcore|hardcore|unknown"
    },
    "risk_success": {
      "success_probability": number,          // 0-100
      "risk_level": "low|moderate|high",
      "ai_summary": "string"
    },
    "revenue_snapshot": {
      "month_1": { "low": number, "mid": number, "high": number },
      "month_3": { "low": number, "mid": number, "high": number }
    }
  },
  "top_niches": [
    {
      "niche_title": "string",
      "trend_direction": "up|stable|down",
      "success_probability": number,           // 0-100
      "risk_score": number,                   // 0-100 (higher = riskier)
      "market_saturation": number,            // 0-100
      "competition_density": number,          // 0-100
      "team_fit_score": number,               // 0-100
      "release_timing": {
        "recommended_window": "string",
        "best_months": ["string"],
        "worst_months": ["string"],
        "visibility_score": number            // 0-100
      },
      "financial_projections": {
        "month_1": { "low": number, "mid": number, "high": number },
        "month_6": { "low": number, "mid": number, "high": number },
        "month_12": { "low": number, "mid": number, "high": number }
      },
      "product_direction": {
        "game_mode": "string",
        "core_theme": "string",
        "recommended_scope": "small|medium|large",
        "core_mechanics": ["string"]
      },
      "publisher_fit": [
        { "publisher": "string", "match_score": number, "example_games": ["string"] }
      ],
      "marketing_plan": {
        "pre_launch": "string",
        "launch": "string",
        "post_launch": "string",
        "primary_channels": ["string"],
        "community_strategy": "string",
        "risks": "string"
      },
      "explainability": {
        "top_success_factors": ["string"],
        "top_risk_factors": ["string"],
        "model_confidence": number            // 0-100
      }
    }
  ]
}

Rules:
- Use provided numeric inputs (ML probs, risk_ratio, trend_delta, publisher_dependency, released_last_6m, deep stats) to justify numbers.
- Keep probabilities realistic. Convert ML prob into 0-100 baseline, then adjust by risk/trend.
- risk_score higher = riskier. Use risk_ratio (bigger ratio = riskier) and publisher_dependency to raise risk.
- trend_direction: use trend_delta (positive => up, near 0 => stable, negative => down).
- If you don't know something, set "unknown" or reasonable defaults, but DO NOT omit fields.
""".strip()


def _safe_int(x: Any, default: int = 0) -> int:
    try:
        return int(x)
    except Exception:
        return default


def _safe_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default


def _default_response(chat_name: str) -> Dict[str, Any]:
    return {
        "chatName": chat_name,
        "summary": {
            "recommended_niche": "Indie",
            "core_theme": "unknown",
            "game_mode": "unknown",
            "recommended_release_window": "unknown",
            "target_audience": {"age_range": {"min": 18, "max": 35}, "player_type": "midcore"},
            "risk_success": {
                "success_probability": 50.0,
                "risk_level": "moderate",
                "ai_summary": "Fallback response (LLM unavailable or invalid JSON).",
            },
            "revenue_snapshot": {"month_1": {"low": 0, "mid": 0, "high": 0}, "month_3": {"low": 0, "mid": 0, "high": 0}},
        },
        "top_niches": [],
    }


async def _call_perplexity_json(prompt: str, timeout: float = 120.0) -> Dict[str, Any]:
    url = f"{settings.PERPLEXITY_BASE_URL.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.PERPLEXITY_API_KEY}",
        "Content-Type": "application/json",
    }
    body = {
        "model": settings.PERPLEXITY_MODEL,
        "messages": [
            {"role": "system", "content": _SYSTEM_CONTEXT},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
    }

    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(url, headers=headers, json=body)
        r.raise_for_status()
        data = r.json()
        content = data["choices"][0]["message"]["content"]

    # Must be JSON only; still parse defensively
    return _strip_think_blocks(raw)


async def generate_trend_structured_response(prompt: str, chat_name: str, timeout: float = 120.0) -> LlmTrendJsonResult:
    if settings.PERPLEXITY_API_KEY.strip():
        try:
            obj = await _call_perplexity_json(prompt, timeout=timeout)
        except Exception:
            obj = _default_response(chat_name)
    else:
        obj = _default_response(chat_name)

    # Hard normalize: enforce required top-level keys
    if not isinstance(obj, dict):
        obj = _default_response(chat_name)

    obj["chatName"] = str(obj.get("chatName") or chat_name)

    if "summary" not in obj or not isinstance(obj["summary"], dict):
        obj["summary"] = _default_response(chat_name)["summary"]

    if "top_niches" not in obj or not isinstance(obj["top_niches"], list):
        obj["top_niches"] = []

    return LlmTrendJsonResult(chat_name=obj["chatName"], chat_response_json=obj)


def _strip_think_blocks(text: str) -> str:
    if not text:
        return ""

    t = text.strip()

    # 1) Ako postoji kompletan <think>...</think>, izbriši ga
    t = re.sub(r"(?is)<think>.*?</think>", "", t).strip()

    # 2) Ako i dalje počinje sa <think> (bez </think>), skloni sve do kraja
    if t.lower().startswith("<think>"):
        return ""

    # 3) Ako se <think> pojavljuje na početku originala (najčešći slučaj), skloni ga do prve prazne linije ili kraja
    if text.lstrip().lower().startswith("<think>"):
        # probaj da presečeš na duplom newline (posle "thinking" dela često ide normalan odgovor)
        parts = re.split(r"\n\s*\n", text, maxsplit=1)
        if len(parts) == 2:
            return parts[1].strip()
        return ""  # nema ništa posle

    return t