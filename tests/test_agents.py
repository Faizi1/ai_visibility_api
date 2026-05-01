"""
tests/test_agents.py

Unit tests for all three agents.
LLM calls are mocked so tests run instantly without API keys.
We test:
  - Normal happy-path JSON parsing
  - Fallback behavior when LLM returns garbage
  - Opportunity score formula edge cases
"""
import pytest
import json
from unittest.mock import patch, MagicMock


# ── Agent 1 tests ────────────────────────────────────────────────────────────

class TestQueryDiscoveryAgent:

    def _make_agent(self):
        from app.agents.discovery import QueryDiscoveryAgent
        return QueryDiscoveryAgent()

    def _mock_response(self, payload: dict):
        """Build a fake (text, tokens) tuple that _call_llm returns."""
        return json.dumps(payload), 150

    def test_returns_queries_on_valid_response(self):
        agent = self._make_agent()
        fake_output = {
            "queries": [
                {"query_text": "Best SEO content tool 2024?", "commercial_intent": "high", "query_type": "best-of"},
                {"query_text": "Surfer SEO vs Clearscope which is better?", "commercial_intent": "high", "query_type": "comparison"},
            ]
        }
        with patch.object(agent, "_call_llm", return_value=self._mock_response(fake_output)):
            queries, tokens = agent.run(
                domain="surferseo.com",
                name="Surfer SEO",
                industry="SEO Software",
                description="AI SEO tool",
                competitors=["clearscope.io"],
            )

        assert len(queries) == 2
        assert queries[0]["query_text"] == "Best SEO content tool 2024?"
        assert tokens == 150

    def test_falls_back_when_llm_returns_garbage(self):
        agent = self._make_agent()
        with patch.object(agent, "_call_llm", return_value=("not json at all!!!", 50)):
            queries, tokens = agent.run(
                domain="surferseo.com",
                name="Surfer SEO",
                industry="SEO Software",
                description="",
                competitors=["clearscope.io"],
            )

        # Fallback should return at least one query, not crash
        assert isinstance(queries, list)
        assert len(queries) >= 1

    def test_falls_back_when_queries_key_missing(self):
        agent = self._make_agent()
        bad_output = {"wrong_key": []}
        with patch.object(agent, "_call_llm", return_value=(json.dumps(bad_output), 50)):
            queries, _ = agent.run(
                domain="frase.io",
                name="Frase",
                industry="SEO Content",
                description="",
                competitors=[],
            )
        assert isinstance(queries, list)
        assert len(queries) >= 1


# ── Agent 2 tests ────────────────────────────────────────────────────────────

class TestVisibilityScoringAgent:

    def _make_agent(self):
        from app.agents.scoring import VisibilityScoringAgent
        return VisibilityScoringAgent()

    def test_scores_not_visible_query_high(self):
        """A query with no visibility + high volume should score high."""
        agent = self._make_agent()
        llm_payload = {
            "domain_visible": False,
            "visibility_confidence": "high",
            "visibility_position": None,
            "reasoning": "Competitor dominates this query.",
            "competitive_difficulty": 40,
        }
        mock_volumes = {"best seo content tool?": {"search_volume": 5000, "competition": 0.4, "cpc": 2.5}}

        with patch.object(agent, "_call_llm", return_value=(json.dumps(llm_payload), 80)):
            with patch("app.agents.scoring.get_search_volumes", return_value=mock_volumes):
                result, tokens = agent.run(
                    query_text="Best SEO content tool?",
                    domain="frase.io",
                    name="Frase",
                    industry="SEO",
                    competitors=["surferseo.com"],
                )

        assert result["domain_visible"] is False
        assert result["visibility_status"] == "not_visible"
        assert result["opportunity_score"] > 0.5  # should be a good opportunity

    def test_scores_visible_query_lower(self):
        """A query where domain is visible should have lower opportunity score."""
        agent = self._make_agent()
        llm_payload = {
            "domain_visible": True,
            "visibility_confidence": "high",
            "visibility_position": 1,
            "reasoning": "Domain is well known here.",
            "competitive_difficulty": 30,
        }
        mock_volumes = {"frase review": {"search_volume": 800, "competition": 0.3, "cpc": 1.0}}

        with patch.object(agent, "_call_llm", return_value=(json.dumps(llm_payload), 60)):
            with patch("app.agents.scoring.get_search_volumes", return_value=mock_volumes):
                result, _ = agent.run(
                    query_text="Frase review",
                    domain="frase.io",
                    name="Frase",
                    industry="SEO",
                    competitors=[],
                )

        assert result["domain_visible"] is True
        assert result["opportunity_score"] < 0.5  # already visible = low opportunity

    def test_handles_malformed_llm_output(self):
        """Agent 2 must not crash when LLM returns garbage."""
        agent = self._make_agent()
        mock_volumes = {"test query": {"search_volume": 200, "competition": 0.5}}

        with patch.object(agent, "_call_llm", return_value=("TOTALLY BROKEN OUTPUT", 30)):
            with patch("app.agents.scoring.get_search_volumes", return_value=mock_volumes):
                result, _ = agent.run(
                    query_text="test query",
                    domain="example.com",
                    name="Example",
                    industry="Tech",
                    competitors=[],
                )

        # Should return a valid dict with defaults, not crash
        assert "opportunity_score" in result
        assert result["visibility_status"] == "unknown"


# ── Agent 3 tests ────────────────────────────────────────────────────────────

class TestContentRecommendationAgent:

    def _make_agent(self):
        from app.agents.recommendation import ContentRecommendationAgent
        return ContentRecommendationAgent()

    def test_returns_recommendations_on_valid_response(self):
        agent = self._make_agent()
        fake_output = {
            "recommendations": [
                {
                    "query_text": "Best SEO content tool?",
                    "content_type": "comparison_page",
                    "title": "Frase vs Surfer SEO: Which Tool Wins in 2024?",
                    "rationale": "A direct comparison page will help AI associate Frase with this query.",
                    "target_keywords": ["frase vs surfer seo", "seo content tool comparison"],
                    "priority": "high",
                }
            ]
        }
        with patch.object(agent, "_call_llm", return_value=(json.dumps(fake_output), 200)):
            recs, tokens = agent.run(
                domain="frase.io",
                name="Frase",
                industry="SEO Content",
                top_queries=[{"query_text": "Best SEO content tool?", "opportunity_score": 0.82, "commercial_intent": "high"}],
            )

        assert len(recs) == 1
        assert recs[0]["content_type"] == "comparison_page"
        assert recs[0]["priority"] == "high"

    def test_returns_empty_when_no_queries(self):
        agent = self._make_agent()
        recs, tokens = agent.run(domain="x.com", name="X", industry="Tech", top_queries=[])
        assert recs == []
        assert tokens == 0

    def test_fallback_when_llm_crashes(self):
        agent = self._make_agent()
        queries = [{"query_text": "What is frase?", "opportunity_score": 0.4, "commercial_intent": "low"}]
        with patch.object(agent, "_call_llm", return_value=("{bad json", 40)):
            recs, _ = agent.run(domain="frase.io", name="Frase", industry="SEO", top_queries=queries)

        assert isinstance(recs, list)
        assert len(recs) >= 1
        # Fallback always produces a blog_post
        assert recs[0]["content_type"] == "blog_post"


# ── Opportunity Score formula tests ──────────────────────────────────────────

class TestOpportunityScore:

    def test_not_visible_high_volume_scores_high(self):
        from app.utils.scoring import compute_opportunity_score
        score = compute_opportunity_score(
            search_volume=10000,
            competitive_difficulty=30,
            domain_visible=False,
            commercial_intent="high",
        )
        assert score > 0.7, f"Expected > 0.7, got {score}"

    def test_visible_low_volume_scores_low(self):
        from app.utils.scoring import compute_opportunity_score
        score = compute_opportunity_score(
            search_volume=50,
            competitive_difficulty=80,
            domain_visible=True,
            commercial_intent="low",
        )
        assert score < 0.3, f"Expected < 0.3, got {score}"

    def test_score_always_between_0_and_1(self):
        from app.utils.scoring import compute_opportunity_score
        # Extreme values — should never go out of bounds
        s1 = compute_opportunity_score(search_volume=0, competitive_difficulty=100, domain_visible=True, commercial_intent="low")
        s2 = compute_opportunity_score(search_volume=999999, competitive_difficulty=0, domain_visible=False, commercial_intent="high")
        assert 0.0 <= s1 <= 1.0
        assert 0.0 <= s2 <= 1.0

    def test_not_visible_always_beats_visible_same_conditions(self):
        from app.utils.scoring import compute_opportunity_score
        kwargs = dict(search_volume=1000, competitive_difficulty=50, commercial_intent="medium")
        score_gap = compute_opportunity_score(**kwargs, domain_visible=False)
        score_no_gap = compute_opportunity_score(**kwargs, domain_visible=True)
        assert score_gap > score_no_gap
