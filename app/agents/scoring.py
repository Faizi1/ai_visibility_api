"""
Agent 2 — Visibility Scoring Agent
------------------------------------
Given a query and a target domain, this agent:
1. Asks Claude to simulate whether the domain would appear in an AI answer
2. Enriches with real search volume data from DataForSEO
3. Computes the opportunity score using the formula in utils/scoring.py

Design rationale:
- We deliberately use Claude to *simulate* AI visibility (asking "would you mention
  this domain?") rather than scraping a live AI endpoint, which would be fragile
  and rate-limited. This mirrors how real AI visibility tools work today.
- Real search volume comes from DataForSEO, falling back to simulation.
- Agent is designed so per-query failures are isolated — the pipeline continues.
"""
from __future__ import annotations

import structlog
from app.agents.base import BaseAgent
from app.utils.dataforseo import get_search_volumes
from app.utils.scoring import compute_opportunity_score

log = structlog.get_logger()


class VisibilityScoringAgent(BaseAgent):

    MAX_TOKENS = 1024  # scoring responses are shorter

    @property
    def _system_prompt(self) -> str:
        return """You are an AI visibility analyst. Your task is to evaluate whether a specific
business domain would realistically appear in an AI assistant's answer to a given query.

Simulate how a well-calibrated AI assistant (like ChatGPT or Claude) would respond to
the query, then assess whether the target domain would be mentioned.

Consider:
- Is the domain a well-known player in this space?
- Does the query intent match the domain's core offering?
- Are there stronger competitors more likely to be cited?
- Is this a branded query (mentions the domain directly)?

Return ONLY valid JSON. No prose, no markdown fences.

Output schema (strict):
{
  "domain_visible": true | false,
  "visibility_confidence": "high | medium | low",
  "visibility_position": null | 1 | 2 | 3,
  "reasoning": "one sentence explanation",
  "competitive_difficulty": 0-100
}

competitive_difficulty: how hard it is to rank for this query in AI answers.
  0  = trivial (branded query, domain dominates)
  50 = moderate competition
  100 = extremely competitive, dominated by major brands"""

    def run(
        self,
        *,
        query_text: str,
        domain: str,
        name: str,
        industry: str,
        competitors: list[str],
        commercial_intent: str = "medium",
    ) -> tuple[dict, int]:
        """
        Returns (scored_data: dict, tokens_used: int).

        scored_data keys:
            domain_visible, visibility_status, visibility_position,
            competitive_difficulty, estimated_search_volume, opportunity_score
        """
        competitor_str = ", ".join(competitors) if competitors else "none listed"

        user_prompt = f"""Query: "{query_text}"

Target domain: {domain} ({name}) — industry: {industry}
Known competitors in this space: {competitor_str}

Simulate an AI assistant answering this query.
Would {domain} appear in the response? Return the JSON object."""

        log.info("agent2_scoring", query=query_text[:60], domain=domain)
        raw, tokens = self._call_llm(user_prompt)

        try:
            llm_data = self._extract_json(raw)
            domain_visible: bool | None = llm_data.get("domain_visible")
            competitive_difficulty: int = int(llm_data.get("competitive_difficulty", 50))
            visibility_position: int | None = llm_data.get("visibility_position")
        except (ValueError, TypeError) as exc:
            log.warning("agent2_parse_error", error=str(exc), query=query_text[:60])
            domain_visible = None
            competitive_difficulty = 50
            visibility_position = None

        # ── Real search volume from DataForSEO ───────────────────────
        volume_data = get_search_volumes([query_text])
        seo_result = volume_data.get(query_text.lower(), {})
        search_volume: int = seo_result.get("search_volume", 500)
        # Convert DataForSEO competition (0.0–1.0) to difficulty (0–100)
        if "competition" in seo_result:
            competitive_difficulty = int(seo_result["competition"] * 100)

        # ── Opportunity score ─────────────────────────────────────────
        opportunity_score = compute_opportunity_score(
            search_volume=search_volume,
            competitive_difficulty=competitive_difficulty,
            domain_visible=domain_visible,
            commercial_intent=commercial_intent,
        )

        # ── Visibility status string ──────────────────────────────────
        if domain_visible is True:
            visibility_status = "visible"
        elif domain_visible is False:
            visibility_status = "not_visible"
        else:
            visibility_status = "unknown"

        result = {
            "domain_visible": domain_visible,
            "visibility_status": visibility_status,
            "visibility_position": visibility_position,
            "competitive_difficulty": competitive_difficulty,
            "estimated_search_volume": search_volume,
            "opportunity_score": opportunity_score,
        }
        log.info("agent2_done", score=opportunity_score, visible=domain_visible, tokens=tokens)
        return result, tokens
