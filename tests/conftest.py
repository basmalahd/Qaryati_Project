import os

# Tests must not depend on a developer's .env or on a running Postgres.
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("JWT_SECRET_KEY", "t" * 64)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app import models  # noqa: E402,F401  (registers tables)
from app.db.session import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture()
def session_factory():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, autoflush=False)
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
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def auth_headers(client, session_factory):
    """Factory: creates a user with the given role directly in the DB and returns Bearer headers."""
    from app.core.security import hash_password
    from app.models.user import User

    def _make(role: str = "viewer", email: str | None = None) -> dict:
        email = email or f"{role}@example.com"
        with session_factory() as db:
            db.add(User(email=email, full_name=role.title(),
                        hashed_password=hash_password("Password123"), role=role))
            db.commit()
        r = client.post("/api/v1/auth/login", json={"email": email, "password": "Password123"})
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    return _make
