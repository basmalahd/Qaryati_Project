from types import SimpleNamespace
from typing import get_args

import pytest

from app.models.village_name import NAME_TYPES
from app.schemas.village_name import NameType
from tests.helpers import API, make_gov, make_source, make_village


@pytest.fixture()
def ctx(client, auth_headers):
    admin, editor, viewer = auth_headers("admin"), auth_headers("editor"), auth_headers("viewer")
    village = make_village(client, editor, make_gov(client, admin))  # Jinsafut / جينصافوط
    return SimpleNamespace(
        admin=admin, editor=editor, viewer=viewer, vid=village["id"],
        sid=make_source(client, editor), url=f"{API}/villages/{village['id']}/names",
    )


def add(client, ctx, name="جنصافوط", name_type="alternative_spelling", headers=None, **extra):
    body = {"name": name, "name_type": name_type, **extra}
    return client.post(ctx.url, json=body, headers=headers or ctx.editor)


def test_schema_name_types_match_database_constraint():
    assert get_args(NameType) == NAME_TYPES


def test_permissions_create_and_list(client, ctx):
    assert add(client, ctx, headers=ctx.viewer).status_code == 403
    first = add(client, ctx)
    assert first.status_code == 201 and first.json()["source"] is None
    second = add(client, ctx, "Jinsafut Old", "former", language="en", source_id=ctx.sid,
                 period_note="Ottoman period")
    assert second.status_code == 201 and second.json()["source"]["title"] == "PCBS 1997"

    listed = client.get(ctx.url, headers=ctx.viewer).json()
    assert [n["name"] for n in listed] == ["جنصافوط", "Jinsafut Old"]
    assert client.get(ctx.url).status_code == 401


def test_rules(client, ctx):
    same_en = add(client, ctx, "jinsafut")  # case-insensitive match with the current English name
    assert same_en.status_code == 422 and same_en.json()["details"][0]["field"] == "name"
    assert add(client, ctx, "جينصافوط").status_code == 422  # current Arabic name

    assert add(client, ctx).status_code == 201
    dup = add(client, ctx)
    assert dup.status_code == 409
    assert add(client, ctx, name_type="historical").status_code == 201  # same name, other type is fine

    assert add(client, ctx, "x1", source_id=9999).status_code == 422
    assert add(client, ctx, "x2", name_type="nickname").status_code == 422
    assert add(client, ctx, "x3", language="arabic").status_code == 422
    assert client.post(f"{API}/villages/9999/names", json={"name": "x", "name_type": "former"},
                       headers=ctx.editor).status_code == 404


def test_update_delete_and_audit(client, ctx):
    nid = add(client, ctx).json()["id"]
    other = add(client, ctx, "جنصفوط").json()["id"]
    item = f"{ctx.url}/{nid}"

    ok = client.patch(item, json={"period_note": "1940s"}, headers=ctx.editor)
    assert ok.status_code == 200 and ok.json()["period_note"] == "1940s"
    assert client.patch(item, json={"name": "جنصفوط"}, headers=ctx.editor).status_code == 409
    assert client.patch(item, json={"name": None}, headers=ctx.editor).status_code == 422
    assert client.patch(item, json={"name": "jinsafut"}, headers=ctx.editor).status_code == 422
    assert client.patch(f"{ctx.url}/9999", json={"period_note": "x"}, headers=ctx.editor).status_code == 404

    cleared = client.patch(f"{ctx.url}/{other}", json={"source_id": ctx.sid}, headers=ctx.editor)
    assert cleared.json()["source"]["id"] == ctx.sid
    assert client.patch(f"{ctx.url}/{other}", json={"source_id": None}, headers=ctx.editor).json()["source"] is None

    assert client.delete(item, headers=ctx.editor).status_code == 403
    assert client.delete(item, headers=ctx.admin).status_code == 204

    logs = client.get(f"{API}/audit-logs?entity_type=village_name&entity_id={nid}", headers=ctx.admin).json()
    assert [e["action"] for e in logs["items"]] == ["delete", "update", "create"]


def test_deleting_a_village_removes_its_names(client, ctx):
    add(client, ctx)
    assert client.delete(f"{API}/villages/{ctx.vid}", headers=ctx.admin).status_code == 204
    assert client.get(ctx.url, headers=ctx.admin).status_code == 404


def test_elevation_and_area(client, auth_headers):
    admin, editor = auth_headers("admin"), auth_headers("editor")
    gov = make_gov(client, admin)
    v = make_village(client, editor, gov, elevation_m=450.5, area_km2=12.3)
    assert (v["elevation_m"], v["area_km2"]) == (450.5, 12.3)

    url = f"{API}/villages/{v['id']}"
    assert client.patch(url, json={"elevation_m": 5000}, headers=editor).status_code == 422
    assert client.patch(url, json={"elevation_m": -430}, headers=editor).status_code == 200  # Dead Sea level
    assert client.patch(url, json={"area_km2": 0}, headers=editor).status_code == 422
    assert client.patch(url, json={"area_km2": -1}, headers=editor).status_code == 422

    changed = client.patch(url, json={"area_km2": 15.0}, headers=editor).json()
    assert changed["area_km2"] == 15.0 and changed["elevation_m"] == -430

    logs = client.get(f"{API}/audit-logs?entity_type=village&entity_id={v['id']}", headers=admin).json()
    assert logs["items"][0]["changes"] == {"before": {"area_km2": 12.3}, "after": {"area_km2": 15.0}}
