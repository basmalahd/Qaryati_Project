"""Shared pytest fixtures and isolated API test configuration."""

import os
from pathlib import Path

# Must be configured before importing app.main / app.core.config.
# Tests should not depend on local .env files or a running PostgreSQL server.
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("JWT_SECRET_KEY", "t" * 64)
os.environ["APP_ENV"] = "test"
os.environ["CORS_ORIGINS"] = "http://localhost:3000"
# API tests must not compete for a single IP quota. Dedicated rate-limit
# tests explicitly opt in via monkeypatch.setenv("RATE_LIMIT_ENABLED", "true").
os.environ["RATE_LIMIT_ENABLED"] = "false"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, event  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app import models  # noqa: E402,F401  (registers tables)
from app.core.rate_limit import clear_rate_limits  # noqa: E402
from app.db.session import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def isolate_rate_limit_state():
    """Avoid quota state leaking between tests, including dedicated limiter tests."""
    clear_rate_limits()
    yield
    clear_rate_limits()


@pytest.fixture()
def session_factory():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )

    @event.listens_for(engine, "connect")
    def _enforce_foreign_keys(dbapi_connection, _record):
        # PostgreSQL enforces foreign keys; SQLite needs an explicit pragma.
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    try:
        yield sessionmaker(bind=engine, autoflush=False)
    finally:
        engine.dispose()


@pytest.fixture()
def client(session_factory):
    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture()
def auth_headers(client, session_factory):
    """Create a user with a given role and return its Bearer auth header."""
    from app.core.security import hash_password
    from app.models.user import User

    def _make(role: str = "viewer", email: str | None = None) -> dict:
        email = email or f"{role}@example.com"
        with session_factory() as db:
            db.add(
                User(
                    email=email,
                    full_name=role.title(),
                    hashed_password=hash_password("Password123"),
                    role=role,
                )
            )
            db.commit()

        response = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "Password123"},
        )
        assert response.status_code == 200, (
            f"Test login failed with HTTP {response.status_code}: {response.text}"
        )
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    return _make


def pytest_collection_modifyitems(items):
    """Mark tests by their unit/integration directory."""
    tests_dir = Path(__file__).parent
    for item in items:
        folder = Path(item.path).relative_to(tests_dir).parts[0]
        if folder not in ("unit", "integration"):
            raise pytest.UsageError(
                f"{item.nodeid}: put tests in tests/unit or tests/integration"
            )
        item.add_marker(getattr(pytest.mark, folder))
