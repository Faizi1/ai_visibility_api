import uuid
from datetime import datetime, timezone
from app import db


class PipelineRun(db.Model):
    __tablename__ = "pipeline_runs"

    uuid: str = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    profile_uuid: str = db.Column(db.String(36), db.ForeignKey("business_profiles.uuid"), nullable=False)

    # ── Status ───────────────────────────────────────────────────────
    # running | completed | failed
    status: str = db.Column(db.String(50), nullable=False, default="running")

    # ── Pipeline metrics ─────────────────────────────────────────────
    queries_discovered: int = db.Column(db.Integer, default=0)
    queries_scored: int = db.Column(db.Integer, default=0)
    tokens_used: int = db.Column(db.Integer, default=0)
    error_message: str = db.Column(db.Text, nullable=True)

    # ── Timestamps ───────────────────────────────────────────────────
    started_at: datetime = db.Column(
        db.DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    completed_at: datetime = db.Column(db.DateTime(timezone=True), nullable=True)

    # ── Relationships ────────────────────────────────────────────────
    queries = db.relationship("DiscoveredQuery", backref="run", lazy="dynamic")

    def to_dict(self) -> dict:
        return {
            "run_uuid": self.uuid,
            "profile_uuid": self.profile_uuid,
            "status": self.status,
            "queries_discovered": self.queries_discovered,
            "queries_scored": self.queries_scored,
            "tokens_used": self.tokens_used,
            "error_message": self.error_message,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

    def __repr__(self) -> str:
        return f"<PipelineRun {self.uuid} status={self.status}>"
