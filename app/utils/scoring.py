"""
Opportunity Score Formula
--------------------------
Combines four signals into a single 0.0–1.0 score representing how
valuable it would be for the target domain to appear in an AI answer.

Formula (documented for README):
    score = (
        w_volume   * volume_norm        +   # higher volume = higher value
        w_gap      * gap_signal         +   # not appearing = max gap = high opp
        w_ease     * ease_signal        +   # lower difficulty = easier to capture
        w_intent   * intent_signal          # commercial intent multiplier
    )

Weights (tunable):
    w_volume  = 0.30  — raw reach
    w_gap     = 0.35  — the gap IS the opportunity (heaviest weight)
    w_ease    = 0.20  — competitive ease
    w_intent  = 0.15  — commercial intent of query type

Volume normalisation:
    We cap at 50,000 searches/month (99th percentile for niche B2B SaaS).
    log-scale so a jump from 100→1000 matters as much as 10k→100k.

Competitive ease:
    ease = 1 - (difficulty / 100)  — inverted so 0 difficulty = 1.0 ease

Gap signal:
    1.0  if domain_visible is False  (not appearing at all — full gap)
    0.3  if domain_visible is None   (unknown — partial credit)
    0.0  if domain_visible is True   (already visible — low opportunity)

Intent signal:
    high   → 1.0
    medium → 0.6
    low    → 0.2
"""
from __future__ import annotations

import math

WEIGHTS = {
    "volume": 0.30,
    "gap": 0.35,
    "ease": 0.20,
    "intent": 0.15,
}

VOLUME_CAP = 50_000.0  # max monthly searches for normalisation


def compute_opportunity_score(
    *,
    search_volume: int,
    competitive_difficulty: int,       # 0–100
    domain_visible: bool | None,
    commercial_intent: str = "medium", # high | medium | low
) -> float:
    """Return opportunity score in [0.0, 1.0]."""

    # ── Volume normalisation (log scale, capped) ──────────────────
    safe_vol = max(1, min(search_volume, VOLUME_CAP))
    volume_norm = math.log(safe_vol) / math.log(VOLUME_CAP)  # 0.0–1.0

    # ── Competitive ease ──────────────────────────────────────────
    difficulty_clamped = max(0, min(100, competitive_difficulty))
    ease_signal = 1.0 - difficulty_clamped / 100.0

    # ── Gap signal ────────────────────────────────────────────────
    if domain_visible is False:
        gap_signal = 1.0
    elif domain_visible is None:
        gap_signal = 0.3
    else:  # True — already visible
        gap_signal = 0.0

    # ── Commercial intent ─────────────────────────────────────────
    intent_map = {"high": 1.0, "medium": 0.6, "low": 0.2}
    intent_signal = intent_map.get(commercial_intent, 0.6)

    # ── Weighted sum ──────────────────────────────────────────────
    score = (
        WEIGHTS["volume"] * volume_norm
        + WEIGHTS["gap"] * gap_signal
        + WEIGHTS["ease"] * ease_signal
        + WEIGHTS["intent"] * intent_signal
    )

    return round(min(1.0, max(0.0, score)), 4)
