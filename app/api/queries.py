"""
queries.py  —  Blueprint for single-query operations

Routes:
    POST /api/v1/queries/<uuid>/recheck   re-run Agent 2 on a single query
"""

from flask import Blueprint, jsonify
from app import db
from app.models.query import DiscoveredQuery
from app.models.profile import BusinessProfile

queries_bp = Blueprint("queries", __name__)


# ---------------------------------------------------------------------------
# POST /api/v1/queries/<uuid>/recheck
# Re-runs Agent 2 on a single query — useful after you've published content
# ---------------------------------------------------------------------------
@queries_bp.route("/queries/<query_uuid>/recheck", methods=["POST"])
def recheck_query(query_uuid):
    query = DiscoveredQuery.query.get(query_uuid)
    if not query:
        return jsonify({"error": "not_found", "message": "Query not found"}), 404

    # Load the parent profile so Agent 2 has full context
    profile = BusinessProfile.query.get(query.profile_uuid)
    if not profile:
        return jsonify({"error": "not_found", "message": "Parent profile not found"}), 404

    from app.agents.scoring import VisibilityScoringAgent
    agent2 = VisibilityScoringAgent()

    try:
        scored, tokens = agent2.run(
            query_text=query.query_text,
            domain=profile.domain,
            name=profile.name,
            industry=profile.industry,
            competitors=profile.competitors or [],
            commercial_intent=query.commercial_intent,
        )

        # Update the query record with fresh scores
        query.domain_visible = scored["domain_visible"]
        query.visibility_status = scored["visibility_status"]
        query.visibility_position = scored["visibility_position"]
        query.competitive_difficulty = scored["competitive_difficulty"]
        query.estimated_search_volume = scored["estimated_search_volume"]
        query.opportunity_score = scored["opportunity_score"]
        db.session.commit()

        return jsonify({
            "message": "Query re-scored successfully",
            "tokens_used": tokens,
            "query": query.to_dict(),
        }), 200

    except Exception as exc:
        return jsonify({
            "error": "recheck_failed",
            "message": str(exc)
        }), 500
