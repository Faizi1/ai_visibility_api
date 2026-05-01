import uuid
from datetime import datetime, timezone
from app import db


class ContentRecommendation(db.Model):
    __tablename__ = "content_recommendations"

    uuid: str = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    profile_uuid: str = db.Column(db.String(36), db.ForeignKey("business_profiles.uuid"), nullable=False)
    query_uuid: str = db.Column(db.String(36), db.ForeignKey("discovered_queries.uuid"), nullable=False)

    # ── Content metadata ─────────────────────────────────────────────
    # blog_post | landing_page | faq | comparison_page | guide
    content_type: str = db.Column(db.String(50), nullable=False)
    title: str = db.Column(db.String(512), nullable=False)
    rationale: str = db.Column(db.Text, nullable=False)

    # Stored as JSON array of keyword strings
    target_keywords: list = db.Column(db.JSON, nullable=False, default=list)

    # high | medium | low
    priority: str = db.Column(db.String(20), nullable=False, default="medium")

    # ── Timestamp ────────────────────────────────────────────────────
    created_at: datetime = db.Column(
        db.DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    def to_dict(self) -> dict:
        return {
            "recommendation_uuid": self.uuid,
            "target_query_uuid": self.query_uuid,
            "profile_uuid": self.profile_uuid,
            "content_type": self.content_type,
            "title": self.title,
            "rationale": self.rationale,
            "target_keywords": self.target_keywords,
            "priority": self.priority,
            "created_at": self.created_at.isoformat(),
        }

    def __repr__(self) -> str:
        return f"<ContentRecommendation {self.priority} '{self.title[:40]}'>"
