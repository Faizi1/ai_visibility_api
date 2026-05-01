"""
profiles.py  —  Blueprint for business profile + pipeline endpoints

Routes:
    POST   /api/v1/profiles                       register a new business
    GET    /api/v1/profiles/<uuid>                get profile + summary stats
    POST   /api/v1/profiles/<uuid>/run            kick off the 3-agent pipeline
    GET    /api/v1/profiles/<uuid>/queries        list all queries (with filters)
    GET    /api/v1/profiles/<uuid>/recommendations  list content recommendations
"""

from flask import Blueprint, request, jsonify
from app import db, limiter
from app.models.profile import BusinessProfile
from app.models.query import DiscoveredQuery
from app.models.recommendation import ContentRecommendation

profiles_bp = Blueprint("profiles", __name__)


# ---------------------------------------------------------------------------
# POST /api/v1/profiles  — register a new business
# ---------------------------------------------------------------------------
@profiles_bp.route("/profiles", methods=["POST"])
def create_profile():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "bad_request", "message": "JSON body required"}), 400

    # Validate required fields
    required = ["name", "domain", "industry"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"error": "validation_error", "missing_fields": missing}), 400

    # Don't allow duplicate domains
    existing = BusinessProfile.query.filter_by(domain=data["domain"]).first()
    if existing:
        return jsonify({
            "error": "conflict",
            "message": f"A profile for '{data['domain']}' already exists.",
            "profile_uuid": existing.uuid
        }), 409

    profile = BusinessProfile(
        name=data["name"],
        domain=data["domain"],
        industry=data["industry"],
        description=data.get("description", ""),
        competitors=data.get("competitors", []),
        status="created",
    )
    db.session.add(profile)
    db.session.commit()

    return jsonify(profile.to_dict()), 201


# ---------------------------------------------------------------------------
# GET /api/v1/profiles/<uuid>  — fetch profile + summary stats
# ---------------------------------------------------------------------------
@profiles_bp.route("/profiles/<profile_uuid>", methods=["GET"])
def get_profile(profile_uuid):
    profile = BusinessProfile.query.get(profile_uuid)
    if not profile:
        return jsonify({"error": "not_found", "message": "Profile not found"}), 404

    return jsonify(profile.to_dict(include_stats=True)), 200


# ---------------------------------------------------------------------------
# POST /api/v1/profiles/<uuid>/run  — trigger the full pipeline
# Rate-limited to 5 per hour per IP so we don't rack up huge AI bills
# ---------------------------------------------------------------------------
@profiles_bp.route("/profiles/<profile_uuid>/run", methods=["POST"])
@limiter.limit("5 per hour")
def run_pipeline(profile_uuid):
    profile = BusinessProfile.query.get(profile_uuid)
    if not profile:
        return jsonify({"error": "not_found", "message": "Profile not found"}), 404

    # Don't allow two pipelines to run at the same time for the same profile
    if profile.status == "running":
        return jsonify({
            "error": "conflict",
            "message": "A pipeline is already running for this profile."
        }), 409

    profile.status = "running"
    db.session.commit()

    # Import here to avoid circular imports at module level
    from app.services.pipeline import run_pipeline as execute_pipeline

    try:
        result = execute_pipeline(profile)
        return jsonify(result), 200
    except Exception as exc:
        # Pipeline already marks itself failed in DB — just return 500
        return jsonify({
            "error": "pipeline_failed",
            "message": str(exc),
            "run_status": "failed"
        }), 500


# ---------------------------------------------------------------------------
# GET /api/v1/profiles/<uuid>/queries  — list discovered queries
# Supports: ?min_score=0.5  ?status=not_visible  ?page=1&per_page=20
# ---------------------------------------------------------------------------
@profiles_bp.route("/profiles/<profile_uuid>/queries", methods=["GET"])
def list_queries(profile_uuid):
    profile = BusinessProfile.query.get(profile_uuid)
    if not profile:
        return jsonify({"error": "not_found", "message": "Profile not found"}), 404

    # Start building the query
    q = DiscoveredQuery.query.filter_by(profile_uuid=profile_uuid)

    # Filter by minimum opportunity score
    min_score = request.args.get("min_score", type=float)
    if min_score is not None:
        q = q.filter(DiscoveredQuery.opportunity_score >= min_score)

    # Filter by visibility status
    status_filter = request.args.get("status")
    if status_filter in ("visible", "not_visible", "unknown"):
        q = q.filter(DiscoveredQuery.visibility_status == status_filter)

    # Sort best opportunities first
    q = q.order_by(DiscoveredQuery.opportunity_score.desc())

    # Pagination
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 20, type=int), 100)  # cap at 100
    paginated = q.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        "queries": [item.to_dict() for item in paginated.items],
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": paginated.total,
            "pages": paginated.pages,
        }
    }), 200


# ---------------------------------------------------------------------------
# GET /api/v1/profiles/<uuid>/recommendations  — list content recommendations
# ---------------------------------------------------------------------------
@profiles_bp.route("/profiles/<profile_uuid>/recommendations", methods=["GET"])
def list_recommendations(profile_uuid):
    profile = BusinessProfile.query.get(profile_uuid)
    if not profile:
        return jsonify({"error": "not_found", "message": "Profile not found"}), 404

    recs = (
        ContentRecommendation.query
        .filter_by(profile_uuid=profile_uuid)
        .order_by(ContentRecommendation.created_at.desc())
        .all()
    )

    return jsonify({
        "recommendations": [r.to_dict() for r in recs],
        "total": len(recs),
    }), 200
