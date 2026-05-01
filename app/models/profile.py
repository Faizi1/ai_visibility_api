import uuid
from datetime import datetime, timezone
from app import db


class BusinessProfile(db.Model):
    __tablename__ = "business_profiles"

    # ── Primary key ──────────────────────────────────────────────────
    uuid: str = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # ── Core fields ──────────────────────────────────────────────────
    name: str = db.Column(db.String(255), nullable=False)
    domain: str = db.Column(db.String(255), nullable=False, unique=True)
    industry: str = db.Column(db.String(255), nullable=False)
    description: str = db.Column(db.Text, nullable=True)

    # Stored as JSON array e.g. ["clearscope.io", "marketmuse.com"]
    competitors: list = db.Column(db.JSON, nullable=False, default=list)

    # Lifecycle status: created | running | completed | failed
    status: str = db.Column(db.String(50), nullable=False, default="created")

    # ── Timestamps ───────────────────────────────────────────────────
    created_at: datetime = db.Column(
        db.DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = db.Column(
        db.DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    # ── Relationships ────────────────────────────────────────────────
    pipeline_runs = db.relationship("PipelineRun", backref="profile", lazy="dynamic")
    queries = db.relationship("DiscoveredQuery", backref="profile", lazy="dynamic")
    recommendations = db.relationship("ContentRecommendation", backref="profile", lazy="dynamic")

    # ── Computed properties ──────────────────────────────────────────
    @property
    def total_queries(self) -> int:
        return self.queries.count()

    @property
    def avg_opportunity_score(self) -> float | None:
        from sqlalchemy import func
        from app.models.query import DiscoveredQuery
        result = db.session.query(
            func.avg(DiscoveredQuery.opportunity_score)
        ).filter_by(profile_uuid=self.uuid).scalar()
        return round(float(result), 4) if result else None

    def to_dict(self, include_stats: bool = False) -> dict:
        data = {
            "profile_uuid": self.uuid,
            "name": self.name,
            "domain": self.domain,
            "industry": self.industry,
            "description": self.description,
            "competitors": self.competitors,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
        if include_stats:
            data["stats"] = {
                "total_queries_discovered": self.total_queries,
                "avg_opportunity_score": self.avg_opportunity_score,
            }
        return data

    def __repr__(self) -> str:
        return f"<BusinessProfile {self.domain}>"
