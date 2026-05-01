import uuid
from datetime import datetime, timezone
from app import db


class DiscoveredQuery(db.Model):
    __tablename__ = "discovered_queries"

    uuid: str = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    profile_uuid: str = db.Column(db.String(36), db.ForeignKey("business_profiles.uuid"), nullable=False)
    run_uuid: str = db.Column(db.String(36), db.ForeignKey("pipeline_runs.uuid"), nullable=False)

    # ── Query content ────────────────────────────────────────────────
    query_text: str = db.Column(db.Text, nullable=False)

    # ── Scoring fields (populated by Agent 2) ───────────────────────
    estimated_search_volume: int = db.Column(db.Integer, default=0)
    competitive_difficulty: int = db.Column(db.Integer, default=50)   # 0–100
    opportunity_score: float = db.Column(db.Float, default=0.0)        # 0.0–1.0

    # ── Visibility fields (populated by Agent 2) ─────────────────────
    # visible | not_visible | unknown
    domain_visible: bool = db.Column(db.Boolean, nullable=True)
    visibility_status: str = db.Column(db.String(20), default="unknown")
    visibility_position: int = db.Column(db.Integer, nullable=True)    # rank position if visible

    # ── Commercial intent flag ───────────────────────────────────────
    # high | medium | low  (used in opportunity score formula)
    commercial_intent: str = db.Column(db.String(20), default="medium")

    # ── Timestamp ────────────────────────────────────────────────────
    discovered_at: datetime = db.Column(
        db.DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    # ── Relationships ────────────────────────────────────────────────
    recommendations = db.relationship("ContentRecommendation", backref="query", lazy="dynamic")

    def to_dict(self) -> dict:
        return {
            "query_uuid": self.uuid,
            "query_text": self.query_text,
            "estimated_search_volume": self.estimated_search_volume,
            "competitive_difficulty": self.competitive_difficulty,
            "opportunity_score": round(self.opportunity_score, 4),
            "domain_visible": self.domain_visible,
            "visibility_status": self.visibility_status,
            "visibility_position": self.visibility_position,
            "commercial_intent": self.commercial_intent,
            "discovered_at": self.discovered_at.isoformat(),
            "profile_uuid": self.profile_uuid,
            "run_uuid": self.run_uuid,
        }

    def __repr__(self) -> str:
        return f"<DiscoveredQuery score={self.opportunity_score:.2f} '{self.query_text[:40]}'>"
