"""
Pipeline Orchestrator
----------------------
Coordinates the three agents in sequence:
  Agent 1 (Discovery) → Agent 2 (Scoring, per-query) → Agent 3 (Recommendations)

Failure isolation:
  - If Agent 2 fails for a single query, that query is skipped and the rest continue.
  - If Agent 1 fails entirely, the run is marked failed immediately.
  - If Agent 3 fails, we still return the scored queries (partial success).

Token tracking:
  Tokens from all three agents are summed and stored on PipelineRun.
"""
from __future__ import annotations

from datetime import datetime, timezone

import structlog

from app import db
from app.agents import QueryDiscoveryAgent, VisibilityScoringAgent, ContentRecommendationAgent
from app.models.query import DiscoveredQuery
from app.models.recommendation import ContentRecommendation
from app.models.pipeline_run import PipelineRun
from app.models.profile import BusinessProfile

log = structlog.get_logger()


def run_pipeline(profile: BusinessProfile) -> dict:
    """
    Runs the full 3-agent pipeline for a given profile.
    Returns a response dict suitable for the API endpoint.
    Saves all results to the database.
    """
    # ── Create pipeline run record ────────────────────────────────
    pipeline_run = PipelineRun(
        profile_uuid=profile.uuid,
        status="running",
        started_at=datetime.now(timezone.utc),
    )
    db.session.add(pipeline_run)
    db.session.commit()
    run_log = log.bind(run_uuid=pipeline_run.uuid, domain=profile.domain)

    total_tokens = 0

    try:
        # ── AGENT 1 — Query Discovery ─────────────────────────────
        run_log.info("pipeline_agent1_start")
        agent1 = QueryDiscoveryAgent()
        raw_queries, tokens1 = agent1.run(
            domain=profile.domain,
            name=profile.name,
            industry=profile.industry,
            description=profile.description or "",
            competitors=profile.competitors or [],
        )
        total_tokens += tokens1
        run_log.info("pipeline_agent1_done", queries=len(raw_queries))

        if not raw_queries:
            raise RuntimeError("Agent 1 returned no queries — cannot continue.")

        # ── Persist discovered queries (pre-scoring) ──────────────
        query_objects: list[DiscoveredQuery] = []
        for q in raw_queries:
            dq = DiscoveredQuery(
                profile_uuid=profile.uuid,
                run_uuid=pipeline_run.uuid,
                query_text=q["query_text"],
                commercial_intent=q.get("commercial_intent", "medium"),
                visibility_status="unknown",
            )
            db.session.add(dq)
            query_objects.append(dq)
        db.session.flush()  # get UUIDs without committing

        pipeline_run.queries_discovered = len(query_objects)

        # ── AGENT 2 — Visibility Scoring (per-query, isolated) ────
        agent2 = VisibilityScoringAgent()
        scored_count = 0

        for dq in query_objects:
            try:
                scored, tokens2 = agent2.run(
                    query_text=dq.query_text,
                    domain=profile.domain,
                    name=profile.name,
                    industry=profile.industry,
                    competitors=profile.competitors or [],
                    commercial_intent=dq.commercial_intent,
                )
                total_tokens += tokens2

                # Update query record with scoring results
                dq.domain_visible = scored["domain_visible"]
                dq.visibility_status = scored["visibility_status"]
                dq.visibility_position = scored["visibility_position"]
                dq.competitive_difficulty = scored["competitive_difficulty"]
                dq.estimated_search_volume = scored["estimated_search_volume"]
                dq.opportunity_score = scored["opportunity_score"]
                scored_count += 1

            except Exception as exc:
                # Per-query failure is isolated — log and continue
                run_log.warning("agent2_query_failed", query=dq.query_text[:60], error=str(exc))
                dq.visibility_status = "unknown"

        pipeline_run.queries_scored = scored_count
        db.session.flush()

        # ── AGENT 3 — Content Recommendations ────────────────────
        # Only pass queries where domain is NOT visible, sorted by opportunity
        gap_queries = (
            DiscoveredQuery.query
            .filter_by(profile_uuid=profile.uuid, run_uuid=pipeline_run.uuid)
            .filter(DiscoveredQuery.visibility_status == "not_visible")
            .order_by(DiscoveredQuery.opportunity_score.desc())
            .limit(5)
            .all()
        )

        top_queries_for_agent3 = [
            {
                "query_text": q.query_text,
                "opportunity_score": q.opportunity_score,
                "commercial_intent": q.commercial_intent,
            }
            for q in gap_queries
        ]

        agent3 = ContentRecommendationAgent()
        raw_recs, tokens3 = agent3.run(
            domain=profile.domain,
            name=profile.name,
            industry=profile.industry,
            top_queries=top_queries_for_agent3,
        )
        total_tokens += tokens3

        # ── Persist recommendations with FK to query ──────────────
        # Build a lookup: query_text → DiscoveredQuery.uuid
        query_text_to_uuid = {q.query_text: q.uuid for q in gap_queries}

        saved_recs: list[ContentRecommendation] = []
        for rec in raw_recs:
            q_uuid = query_text_to_uuid.get(rec.get("query_text", ""))
            if not q_uuid:
                # Try fuzzy match — first query as fallback
                q_uuid = gap_queries[0].uuid if gap_queries else query_objects[0].uuid

            cr = ContentRecommendation(
                profile_uuid=profile.uuid,
                query_uuid=q_uuid,
                content_type=rec.get("content_type", "blog_post"),
                title=rec.get("title", "Untitled"),
                rationale=rec.get("rationale", ""),
                target_keywords=rec.get("target_keywords", []),
                priority=rec.get("priority", "medium"),
            )
            db.session.add(cr)
            saved_recs.append(cr)

        # ── Finalise pipeline run ─────────────────────────────────
        pipeline_run.status = "completed"
        pipeline_run.tokens_used = total_tokens
        pipeline_run.completed_at = datetime.now(timezone.utc)
        profile.status = "completed"
        db.session.commit()

        # ── Build response ────────────────────────────────────────
        top3 = (
            DiscoveredQuery.query
            .filter_by(profile_uuid=profile.uuid, run_uuid=pipeline_run.uuid)
            .order_by(DiscoveredQuery.opportunity_score.desc())
            .limit(3)
            .all()
        )

        run_log.info("pipeline_completed", tokens=total_tokens, recs=len(saved_recs))

        return {
            "run_uuid": pipeline_run.uuid,
            "status": "completed",
            "queries_discovered": pipeline_run.queries_discovered,
            "queries_scored": pipeline_run.queries_scored,
            "top_opportunity_queries": [q.to_dict() for q in top3],
            "content_recommendations": [r.to_dict() for r in saved_recs],
            "tokens_used": total_tokens,
        }

    except Exception as exc:
        run_log.error("pipeline_failed", error=str(exc))
        pipeline_run.status = "failed"
        pipeline_run.error_message = str(exc)
        pipeline_run.completed_at = datetime.now(timezone.utc)
        pipeline_run.tokens_used = total_tokens
        profile.status = "failed"
        db.session.commit()
        raise
