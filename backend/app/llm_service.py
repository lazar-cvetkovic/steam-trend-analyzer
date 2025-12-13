from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests

from .settings import settings

@dataclass(frozen=True)
class LlmResult:
    full_text: str
    action_plan_text: str

_SYSTEM_CONTEXT = """
You are an expert Steam market analyst and game producer.
You will be given:
- user constraints (team size, dev time, experience, art heaviness, revenue expectations)
- quantitative tag market data (trends, deep stats, top games)
- ML tag probabilities for success

Return:
1) A short data-backed explanation of what tag direction to pursue and why (cite numbers).
2) A clear step-by-step action plan (8-12 steps) the team can execute.
Keep it concise and practical. Use bullet points. Use concrete thresholds where possible.
""".strip()

def _extract_action_plan(full_text: str) -> str:
    marker = "Action Plan:"
    idx = full_text.lower().find(marker.lower())
    if idx == -1:
        return full_text.strip()
    return full_text[idx + len(marker):].strip()

def call_perplexity(prompt: str) -> str:
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
    r = requests.post(url, headers=headers, data=json.dumps(body), timeout=60)
    r.raise_for_status()
    data = r.json()
    return data["choices"][0]["message"]["content"]

def generate_trend_response(prompt: str) -> LlmResult:
    if settings.PERPLEXITY_API_KEY.strip():
        text = call_perplexity(prompt)
    else:
        # Mock response if no API key provided
        text = (
            "Data-backed summary:\n"
            "- Your constraints suggest focusing on the top predicted tag and validating demand quickly.\n"
            "- Use the deep data stats (price median/avg, platform %, publisher %) as guardrails.\n\n"
            "Action Plan:\n"
            "1) Pick 1 primary tag + 2 secondary tags from ML top list.\n"
            "2) Validate by comparing top-20 revenue titles and their common features.\n"
            "3) Define MVP scope to fit max dev months.\n"
            "4) Set wishlist target milestones.\n"
            "5) Ship a demo + iterate based on feedback.\n"
        )

    return LlmResult(full_text=text.strip(), action_plan_text=_extract_action_plan(text))
