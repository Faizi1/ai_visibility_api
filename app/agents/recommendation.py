"""
Agent 3 — Content Recommendation Agent
-----------------------------------------
Given the top-scoring queries where the target domain is NOT visible,
this agent generates 3-5 specific, actionable content recommendations.

Design rationale:
- Input is pre-filtered to only "not_visible" queries, ranked by opportunity score.
  This keeps the prompt focused and the output directly actionable.
- We batch all top queries in one prompt (rather than one call per query) to
  reduce latency and token usage — a deliberate efficiency tradeoff.
- Output is one recommendation per query so the FK relationship is clean.
"""
from __future__ import annotations

import structlog
from app.agents.base import BaseAgent

log = structlog.get_logger()

# How many top queries to pass to Agent 3
TOP_N_QUERIES = 5


class ContentRecommendationAgent(BaseAgent):

    MAX_TOKENS = 3000  # recommendations need more tokens

    @property
    def _system_prompt(self) -> str:
        return """You are a senior content strategist specialising in AI search optimisation (AISO).
Your job is to generate specific, actionable content recommendations that will help a business
appear in AI-generated answers for high-value queries where they are currently NOT appearing.

Each recommendation must:
1. State exactly what content to create (title, type)
2. Explain WHY this content addresses the visibility gap
3. List 3-6 specific keywords/topics the content must cover
4. Assign a priority based on opportunity score and effort

Content types available: blog_post, landing_page, faq, comparison_page, guide, case_study

Priority assignment:
  high   — opportunity_score > 0.65 OR comparison/best-of query type
  medium — opportunity_score 0.35–0.65
  low    — opportunity_score < 0.35

Return ONLY valid JSON. No prose, no markdown.

Output schema (strict):
{
  "recommendations": [
    {
      "query_text": "the exact query this recommendation addresses",
      "content_type": "blog_post | landing_page | faq | comparison_page | guide | case_study",
      "title": "specific suggested title for the content piece",
      "rationale": "2-3 sentences explaining why this content closes the visibility gap",
      "target_keywords": ["keyword1", "keyword2", "keyword3"],
      "priority": "high | medium | low"
    }
  ]
}"""

    def run(
        self,
        *,
        domain: str,
        name: str,
        industry: str,
        top_queries: list[dict],  # [{query_text, opportunity_score, commercial_intent, ...}]
    ) -> tuple[list[dict], int]:
        """
        Returns (recommendations: list[dict], tokens_used: int).
        Recommendations are already matched to query_text for FK resolution.
        """
        if not top_queries:
            log.info("agent3_skipped", reason="no qualifying queries")
            return [], 0

        queries_for_prompt = top_queries[:TOP_N_QUERIES]
        queries_block = "\n".join(
            f"  - \"{q['query_text']}\" (opportunity_score={q.get('opportunity_score', 0):.2f}, "
            f"intent={q.get('commercial_intent', 'medium')})"
            for q in queries_for_prompt
        )

        user_prompt = f"""Generate content recommendations for {name} ({domain}) in the {industry} industry.

These are the top queries where {domain} is NOT currently appearing in AI answers:
{queries_block}

For EACH query above, create one specific, actionable content recommendation.
Return the JSON object with {len(queries_for_prompt)} recommendations."""

        log.info("agent3_starting", queries=len(queries_for_prompt), domain=domain)
        raw, tokens = self._call_llm(user_prompt)

        try:
            data = self._extract_json(raw)
            recs = data.get("recommendations", [])
            if not isinstance(recs, list):
                raise ValueError("'recommendations' is not a list")
        except (ValueError, AttributeError) as exc:
            log.error("agent3_parse_error", error=str(exc), raw_preview=raw[:200])
            recs = self._fallback_recommendations(name, queries_for_prompt)

        log.info("agent3_done", recommendations=len(recs), tokens=tokens)
        return recs, tokens

    @staticmethod
    def _fallback_recommendations(name: str, queries: list[dict]) -> list[dict]:
        """Minimal fallback when LLM output is unparseable."""
        return [
            {
                "query_text": q["query_text"],
                "content_type": "blog_post",
                "title": f"How {name} Helps With: {q['query_text'][:60]}",
                "rationale": "A dedicated content piece will help AI assistants associate this domain with the query topic.",
                "target_keywords": [q["query_text"].lower()],
                "priority": "medium",
            }
            for q in queries
        ]
