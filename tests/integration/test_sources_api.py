from typing import get_args

from app.models.source import SOURCE_TYPES
from app.schemas.source import SourceType
from tests.helpers import API


def test_schema_source_types_match_database_constraint():
    assert get_args(SourceType) == SOURCE_TYPES


def test_create_permissions_and_validation(client, auth_headers):
    editor, viewer = auth_headers("editor"), auth_headers("viewer")
    body = {"title": "PCBS Census 1997", "source_type": "census", "publication_year": 1997}

    assert client.post(f"{API}/sources", json=body, headers=viewer).status_code == 403
    r = client.post(f"{API}/sources", json=body, headers=editor)
    assert r.status_code == 201 and r.json()["source_type"] == "census"

    assert client.post(f"{API}/sources", json={**body, "source_type": "rumour"}, headers=editor).status_code == 422
    assert client.post(f"{API}/sources", json={**body, "url": "ftp://x"}, headers=editor).status_code == 422
    assert client.post(f"{API}/sources", json={"title": "  "}, headers=editor).status_code == 422
    default = client.post(f"{API}/sources", json={"title": "Untyped"}, headers=editor)
    assert default.json()["source_type"] == "other"


def test_list_filter_search_and_get(client, auth_headers):
    editor = auth_headers("editor")
    for title, t in [("PCBS Census 1997", "census"), ("Village Book", "book"), ("Council site", "website")]:
        client.post(f"{API}/sources", json={"title": title, "source_type": t}, headers=editor)

    everything = client.get(f"{API}/sources", headers=editor).json()
    assert everything["total"] == 3
    assert client.get(f"{API}/sources?source_type=book", headers=editor).json()["total"] == 1
    assert client.get(f"{API}/sources?q=census", headers=editor).json()["total"] == 1
    assert client.get(f"{API}/sources?q=%25", headers=editor).json()["total"] == 0
    assert client.get(f"{API}/sources?page_size=2", headers=editor).json()["total_pages"] == 2

    sid = everything["items"][0]["id"]
    assert client.get(f"{API}/sources/{sid}", headers=editor).status_code == 200
    assert client.get(f"{API}/sources/9999", headers=editor).status_code == 404


def test_patch_and_audit(client, auth_headers):
    admin, editor = auth_headers("admin"), auth_headers("editor")
    sid = client.post(f"{API}/sources", json={"title": "Old title"}, headers=editor).json()["id"]

    r = client.patch(f"{API}/sources/{sid}", json={"title": "New title"}, headers=editor)
    assert r.status_code == 200 and r.json()["title"] == "New title"
    assert client.patch(f"{API}/sources/{sid}", json={"title": None}, headers=editor).status_code == 422

    logs = client.get(f"{API}/audit-logs?entity_type=source&entity_id={sid}", headers=admin).json()
    assert [e["action"] for e in logs["items"]] == ["update", "create"]
    assert logs["items"][0]["changes"] == {"before": {"title": "Old title"}, "after": {"title": "New title"}}
