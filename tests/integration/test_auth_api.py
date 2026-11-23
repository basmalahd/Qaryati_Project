from app.core.security import hash_password
from app.models.user import User

API = "/api/v1"
ERROR_KEYS = {"timestamp", "status", "code", "message", "details", "traceId"}


def register(client, email="ali@example.com", password="Password123", name="Ali"):
    return client.post(f"{API}/auth/register",
                       json={"email": email, "password": password, "full_name": name})


def login(client, email="ali@example.com", password="Password123"):
    return client.post(f"{API}/auth/login", json={"email": email, "password": password})


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def make_admin(session_factory):
    with session_factory() as db:
        db.add(User(email="admin@example.com", full_name="Admin",
                    hashed_password=hash_password("AdminPass123"), role="admin"))
        db.commit()


def test_register_creates_viewer_and_hides_password(client):
    r = register(client)
    assert r.status_code == 201
    body = r.json()
    assert body["role"] == "viewer"
    assert "password" not in body and "hashed_password" not in body


def test_register_duplicate_email_is_409_with_unified_error(client):
    register(client)
    r = register(client, email="ALI@example.com")  # case-insensitive
    assert r.status_code == 409
    assert set(r.json()) == ERROR_KEYS
    assert r.json()["code"] == "CONFLICT"


def test_register_weak_password_is_422_with_field_details(client):
    r = register(client, password="short")
    assert r.status_code == 422
    body = r.json()
    assert set(body) == ERROR_KEYS and body["code"] == "VALIDATION_ERROR"
    assert body["details"][0]["field"] == "password"


def test_login_success_and_wrong_password(client):
    register(client)
    ok = login(client)
    assert ok.status_code == 200
    assert {"access_token", "refresh_token", "token_type", "expires_in"} <= set(ok.json())

    bad = login(client, password="WrongPassword1")
    assert bad.status_code == 401
    assert bad.headers["www-authenticate"] == "Bearer"

    unknown = login(client, email="nobody@example.com")
    assert unknown.status_code == 401
    assert unknown.json()["message"] == bad.json()["message"]  # no user enumeration


def test_me_requires_valid_token(client):
    assert client.get(f"{API}/users/me").status_code == 401
    assert client.get(f"{API}/users/me", headers=bearer("garbage")).status_code == 401

    register(client)
    token = login(client).json()["access_token"]
    r = client.get(f"{API}/users/me", headers=bearer(token))
    assert r.status_code == 200 and r.json()["email"] == "ali@example.com"


def test_viewer_cannot_change_roles_but_admin_can(client, session_factory):
    register(client)
    viewer_token = login(client).json()["access_token"]
    r = client.patch(f"{API}/users/1/role", json={"role": "editor"}, headers=bearer(viewer_token))
    assert r.status_code == 403 and r.json()["code"] == "FORBIDDEN"

    make_admin(session_factory)
    admin_token = login(client, "admin@example.com", "AdminPass123").json()["access_token"]
    r = client.patch(f"{API}/users/1/role", json={"role": "editor"}, headers=bearer(admin_token))
    assert r.status_code == 200 and r.json()["role"] == "editor"

    missing = client.patch(f"{API}/users/999/role", json={"role": "editor"},
                           headers=bearer(admin_token))
    assert missing.status_code == 404


def test_refresh_flow(client):
    register(client)
    tokens = login(client).json()
    r = client.post(f"{API}/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r.status_code == 200

    # an access token must not be usable as a refresh token
    bad = client.post(f"{API}/auth/refresh", json={"refresh_token": tokens["access_token"]})
    assert bad.status_code == 401


def test_unknown_route_uses_unified_error_and_request_id(client):
    r = client.get(f"{API}/nope", headers={"X-Request-ID": "abc123"})
    assert r.status_code == 404
    assert set(r.json()) == ERROR_KEYS
    assert r.json()["traceId"] == "abc123"
    assert r.headers["x-request-id"] == "abc123"
