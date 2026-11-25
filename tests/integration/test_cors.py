import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.cors import configure_cors

ALLOWED = "https://app.qaryati.ps"
OTHER = "https://evil.test"


def make_client(cors_origins: str) -> TestClient:
    settings = Settings(
        _env_file=None,
        database_url="sqlite://",
        jwt_secret_key="k9Zp3QvT7xLw2NfB8mRc5YdH1sJgA6eU4oVi0XtE",
        cors_origins=cors_origins,
    )
    app = FastAPI()
    configure_cors(app, settings)

    @app.get("/ping")
    def ping():
        return {"ok": True}

    return TestClient(app)


@pytest.fixture()
def cors_client():
    return make_client(f"{ALLOWED},https://admin.qaryati.ps")


def preflight(client, origin, method="GET", headers="Authorization"):
    return client.options(
        "/ping",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": method,
            "Access-Control-Request-Headers": headers,
        },
    )


def test_preflight_from_allowed_origin_is_accepted(cors_client):
    r = preflight(cors_client, ALLOWED, method="PATCH", headers="Authorization, Content-Type")
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == ALLOWED
    assert "PATCH" in r.headers["access-control-allow-methods"]
    assert "authorization" in r.headers["access-control-allow-headers"].lower()
    assert r.headers["access-control-max-age"] == "600"


def test_every_configured_origin_is_allowed(cors_client):
    r = preflight(cors_client, "https://admin.qaryati.ps")
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == "https://admin.qaryati.ps"


def test_preflight_from_unknown_origin_is_refused(cors_client):
    r = preflight(cors_client, OTHER)
    assert r.status_code == 400
    assert "access-control-allow-origin" not in r.headers


def test_preflight_with_disallowed_method_is_refused(cors_client):
    r = preflight(cors_client, ALLOWED, method="PUT")
    assert r.status_code == 400


def test_preflight_with_disallowed_header_is_refused(cors_client):
    r = preflight(cors_client, ALLOWED, headers="X-Not-Allowed")
    assert r.status_code == 400


def test_actual_request_from_allowed_origin_gets_cors_headers(cors_client):
    r = cors_client.get("/ping", headers={"Origin": ALLOWED})
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == ALLOWED
    assert "X-Request-ID" in r.headers["access-control-expose-headers"]


def test_actual_request_from_unknown_origin_gets_no_cors_headers(cors_client):
    r = cors_client.get("/ping", headers={"Origin": OTHER})
    assert "access-control-allow-origin" not in r.headers


def test_request_without_origin_gets_no_cors_headers(cors_client):
    assert "access-control-allow-origin" not in cors_client.get("/ping").headers


def test_credentials_are_not_allowed(cors_client):
    r = cors_client.get("/ping", headers={"Origin": ALLOWED})
    assert "access-control-allow-credentials" not in r.headers


def test_empty_origin_list_allows_no_cross_origin_access():
    client = make_client("")
    assert preflight(client, ALLOWED).status_code == 400
    assert "access-control-allow-origin" not in client.get("/ping", headers={"Origin": ALLOWED}).headers


# --- the real application, configured by the test environment (see tests/conftest.py) ---------

def test_real_app_answers_preflight_for_a_configured_origin(client):
    r = client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Authorization",
        },
    )
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_real_app_rejects_preflight_from_unknown_origin(client):
    r = client.options(
        "/api/v1/health",
        headers={"Origin": OTHER, "Access-Control-Request-Method": "GET"},
    )
    assert r.status_code == 400


def test_real_app_keeps_request_id_header_with_cors(client):
    r = client.get("/api/v1/health", headers={"Origin": "http://localhost:3000"})
    assert r.status_code == 200
    assert r.headers["x-request-id"]
    assert r.headers["access-control-allow-origin"] == "http://localhost:3000"
