"""
Agent 1 — Query Discovery Agent
--------------------------------
Given a business profile (domain, industry, competitors, description),
generates 10-20 realistic questions that real users ask AI assistants
when searching for products/services in that competitive space.

Design rationale:
- Uses Claude claude-opus-4-5 for creative, high-quality question generation.
- System prompt enforces strict JSON output schema so parsing never crashes.
- Questions are skewed toward commercial-intent queries (comparisons, best-of,
  "vs" questions) because those are highest value for AI visibility.
"""
from __future__ import annotations

import structlog
from app.agents.base import BaseAgent

log = structlog.get_logger()


class QueryDiscoveryAgent(BaseAgent):

    @property
    def _system_prompt(self) -> str:
        return """You are an expert AI search analyst specialising in commercial query research.
Your job is to generate realistic questions that business decision-makers and end-users
ask AI assistants (ChatGPT, Claude, Perplexity, Gemini) when evaluating products or
services in a given industry.

Rules:
1. Return ONLY valid JSON — no prose, no markdown, no explanations.
2. Generate between 10 and 20 questions.
3. Skew toward high commercial intent:
   - Comparison queries ("X vs Y", "best X for Y")
   - Evaluation queries ("Is X worth it?", "X alternatives")
   - How-to queries that imply product need
4. Each question must feel natural — as if typed into an AI chatbot.
5. Include competitor names where realistic.

Output schema (strict):
{
  "queries": [
    {
      "query_text": "string — the full natural-language question",
      "commercial_intent": "high | medium | low",
      "query_type": "comparison | best-of | how-to | definition | evaluation"
    }
  ]
}"""

    def run(
        self,
        *,
        domain: str,
        name: str,
        industry: str,
        description: str,
        competitors: list[str],
    ) -> tuple[list[dict], int]:
        """
        Returns (queries: list[dict], tokens_used: int).
        Each query dict: {query_text, commercial_intent, query_type}
        """
        competitor_str = ", ".join(competitors) if competitors else "no known competitors"

        user_prompt = f"""Generate 10-20 high-value AI search queries for the following business:

Business name: {name}
Domain: {domain}
Industry: {industry}
Description: {description}
Key competitors: {competitor_str}

Generate questions people would ask AI assistants when researching {industry} tools.
Include direct comparison queries against {competitor_str}.
Return the JSON object only."""

        log.info("agent1_starting", domain=domain, industry=industry)
        raw, tokens = self._call_llm(user_prompt)

        try:
            data = self._extract_json(raw)
            queries = data.get("queries", [])
            if not isinstance(queries, list) or len(queries) == 0:
                raise ValueError("Empty or missing 'queries' key in Agent 1 response")
        except (ValueError, AttributeError) as exc:
            log.error("agent1_parse_error", error=str(exc), raw_preview=raw[:200])
            # Graceful fallback — return a minimal set rather than crashing pipeline
            queries = self._fallback_queries(name, domain, competitors)

        log.info("agent1_done", discovered=len(queries), tokens=tokens)
        return queries, tokens

    @staticmethod
    def _fallback_queries(name: str, domain: str, competitors: list[str]) -> list[dict]:
        """Return generic but useful queries when LLM output is unparseable."""
        base = [
            {"query_text": f"What is {name}?", "commercial_intent": "low", "query_type": "definition"},
            {"query_text": f"Is {name} worth it?", "commercial_intent": "high", "query_type": "evaluation"},
            {"query_text": f"Best alternatives to {domain}", "commercial_intent": "high", "query_type": "best-of"},
        ]
        for comp in competitors[:3]:
            base.append({
                "query_text": f"{name} vs {comp} — which is better?",
                "commercial_intent": "high",
                "query_type": "comparison",
            })
        return base
