import structlog
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

db = SQLAlchemy()
migrate = Migrate()
limiter = Limiter(key_func=get_remote_address)
log = structlog.get_logger()


def create_app(config: dict | None = None) -> Flask:
    """Application factory — creates and configures the Flask app."""
    app = Flask(__name__)

    # ── Default config ──────────────────────────────────────────────
    import os
    from dotenv import load_dotenv
    load_dotenv()

    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///dev.db")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret")

    if config:
        app.config.update(config)

    # ── Extensions ───────────────────────────────────────────────────
    db.init_app(app)
    migrate.init_app(app, db)
    limiter.init_app(app)

    # ── Register models (so migrate sees them) ───────────────────────
    from app.models import profile, query, recommendation, pipeline_run  # noqa: F401

    # ── Blueprints ───────────────────────────────────────────────────
    from app.api.profiles import profiles_bp
    from app.api.queries import queries_bp

    app.register_blueprint(profiles_bp, url_prefix="/api/v1")
    app.register_blueprint(queries_bp, url_prefix="/api/v1")

    # ── Global error handlers ────────────────────────────────────────
    from app.api.errors import register_error_handlers
    register_error_handlers(app)

    log.info("app_created", env=app.config.get("FLASK_ENV", "production"))
    return app
