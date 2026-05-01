"""
DataForSEO API integration — real keyword search volume & competition data.
Used by Agent 2 (VisibilityScoringAgent) to enrich discovered queries.

Docs: https://docs.dataforseo.com/v3/keywords_data/google/search_volume/live/
Free trial available at app.dataforseo.com
"""
from __future__ import annotations

import os
import requests
import structlog

log = structlog.get_logger()

BASE_URL = "https://api.dataforseo.com/v3"


def _auth() -> tuple[str, str]:
    login = os.getenv("DATAFORSEO_LOGIN", "")
    password = os.getenv("DATAFORSEO_PASSWORD", "")
    return login, password


def get_search_volumes(keywords: list[str], location_code: int = 2840) -> dict[str, dict]:
    """
    Fetch real search volume and competition data from DataForSEO.
    Returns dict keyed by keyword: {search_volume, competition, cpc}

    location_code 2840 = United States
    Falls back to simulated data if API credentials are missing/invalid.
    """
    login, password = _auth()
    if not login or not password:
        log.warning("dataforseo_no_credentials", note="using simulated volumes")
        return _simulate_volumes(keywords)

    payload = [
        {
            "keywords": keywords[:50],          # API limit per request
            "location_code": location_code,
            "language_code": "en",
        }
    ]

    try:
        resp = requests.post(
            f"{BASE_URL}/keywords_data/google_ads/search_volume/live",
            json=payload,
            auth=(login, password),
            timeout=30,
        )
        resp.raise_for_status()
        result = resp.json()

        data: dict[str, dict] = {}
        for task in result.get("tasks", []):
            for item in (task.get("result") or []):
                kw = item.get("keyword", "").lower()
                data[kw] = {
                    "search_volume": item.get("search_volume") or 0,
                    "competition": item.get("competition") or 0.5,   # 0.0–1.0
                    "cpc": item.get("cpc") or 0.0,
                }
        log.info("dataforseo_success", fetched=len(data))
        return data

    except Exception as exc:
        log.error("dataforseo_error", error=str(exc), note="falling back to simulation")
        return _simulate_volumes(keywords)


def _simulate_volumes(keywords: list[str]) -> dict[str, dict]:
    """
    Deterministic simulation so the pipeline works without DataForSEO creds.
    Volume is derived from keyword length (shorter = more popular) + intent signals.
    This is clearly marked as simulated in logs.
    """
    log.info("simulating_search_volumes", count=len(keywords))
    HIGH_INTENT_SIGNALS = {"best", "vs", "compare", "top", "review", "alternative", "pricing"}

    result: dict[str, dict] = {}
    for kw in keywords:
        words = kw.lower().split()
        # Shorter queries → higher volume
        base = max(100, 5000 - len(words) * 200)
        # Boost for commercial signals
        if any(sig in words for sig in HIGH_INTENT_SIGNALS):
            base = int(base * 1.8)
        # Add deterministic variance from keyword hash
        variance = (hash(kw) % 1000)
        volume = max(50, base + variance)

        competition = min(0.95, 0.3 + len(words) * 0.05 + (hash(kw) % 100) / 200)

        result[kw.lower()] = {
            "search_volume": volume,
            "competition": round(competition, 2),
            "cpc": round(0.5 + competition * 3.5, 2),
        }
    return result
