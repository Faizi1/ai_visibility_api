"""
conftest.py — shared pytest fixtures

The app fixture spins up a fresh in-memory SQLite database for every test.
This means tests never touch your real dev.db.
"""
import pytest
from app import create_app, db as _db


@pytest.fixture(scope="session")
def app():
    """Create a test Flask app with a separate in-memory database."""
    test_config = {
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "RATELIMIT_ENABLED": False,   # disable rate limiter during tests
    }
    flask_app = create_app(config=test_config)

    with flask_app.app_context():
        _db.create_all()
        yield flask_app
        _db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def db(app):
    """Provide the db object inside an app context."""
    with app.app_context():
        yield _db
