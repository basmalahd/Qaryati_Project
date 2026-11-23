from types import SimpleNamespace

import pytest

from tests.helpers import API, make_gov, make_source, make_village


@pytest.fixture()
def ctx(client, auth_headers):
    admin, editor, viewer = auth_headers("admin"), auth_headers("editor"), auth_headers("viewer")
    gov = make_gov(client, admin)
    a = make_village(client, editor, gov, slug="a-village", name_ar="أ", name_en="Alpha")
    b = make_village(client, editor, gov, slug="b-village", name_ar="ب", name_en="Beta")
    return SimpleNamespace(
        admin=admin, editor=editor, viewer=viewer, a=a["id"], b=b["id"],
        sid=make_source(client, editor), url=f"{API}/villages/{a['id']}/nearby",
    )


def link(client, ctx, headers=None, **body):
    return client.post(ctx.url, json=body, headers=headers or ctx.editor)


def test_create_list_and_permissions(client, ctx):
    body = {"related_village_id": ctx.b, "relation_type": "borders", "distance_km": 2.5, "direction": "N"}
    assert link(client, ctx, headers=ctx.viewer, **body).status_code == 403

    r = link(client, ctx, source_id=ctx.sid, **body)
    assert r.status_code == 201
    assert r.json()["related_village"]["slug"] == "b-village"
    assert r.json()["source"]["title"] == "PCBS 1997"

    city = link(client, ctx, place_name="Qalqilya city", relation_type="nearest_city", distance_km=6)
    assert city.status_code == 201 and city.json()["related_village"] is None

    listed = client.get(ctx.url, headers=ctx.viewer).json()
    assert [(x["relation_type"], x["place_name"]) for x in listed] == [
        ("borders", None), ("nearest_city", "Qalqilya city"),
    ]
    assert client.get(ctx.url).status_code == 401


def test_target_rules(client, ctx):
    both = link(client, ctx, related_village_id=ctx.b, place_name="X", relation_type="nearby")
    assert both.status_code == 422 and both.json()["details"][0]["field"] == "body"
    assert link(client, ctx, relation_type="nearby").status_code == 422  # neither

    me = link(client, ctx, related_village_id=ctx.a, relation_type="nearby")
    assert me.status_code == 422 and me.json()["code"] == "UNPROCESSABLE"
    assert link(client, ctx, related_village_id=9999, relation_type="nearby").status_code == 422
    assert link(client, ctx, related_village_id=ctx.b, relation_type="nearby", source_id=9999).status_code == 422
    assert client.post(f"{API}/villages/9999/nearby", json={"place_name": "x", "relation_type": "nearby"},
                       headers=ctx.editor).status_code == 404


def test_value_validation(client, ctx):
    base = {"related_village_id": ctx.b, "relation_type": "nearby"}
    assert link(client, ctx, **base, distance_km=-1).status_code == 422
    assert link(client, ctx, **base, direction="UP").status_code == 422
    assert link(client, ctx, related_village_id=ctx.b, relation_type="friends").status_code == 422


def test_duplicates_are_rejected(client, ctx):
    assert link(client, ctx, related_village_id=ctx.b, relation_type="borders").status_code == 201
    assert link(client, ctx, related_village_id=ctx.b, relation_type="borders").status_code == 409
    assert link(client, ctx, related_village_id=ctx.b, relation_type="nearby").status_code == 201

    assert link(client, ctx, place_name="Nablus", relation_type="nearest_city").status_code == 201
    assert link(client, ctx, place_name="Nablus", relation_type="nearest_city").status_code == 409
    assert link(client, ctx, place_name="Nablus", relation_type="nearby").status_code == 201


def test_relations_are_directional(client, ctx):
    link(client, ctx, related_village_id=ctx.b, relation_type="borders")
    from_b = client.get(f"{API}/villages/{ctx.b}/nearby", headers=ctx.viewer).json()
    assert from_b == []  # nothing is mirrored behind the scenes


def test_delete_audit_and_cascade(client, ctx):
    rid = link(client, ctx, related_village_id=ctx.b, relation_type="borders").json()["id"]
    assert client.delete(f"{ctx.url}/{rid}", headers=ctx.editor).status_code == 403
    assert client.delete(f"{ctx.url}/{rid}", headers=ctx.admin).status_code == 204
    assert client.delete(f"{ctx.url}/{rid}", headers=ctx.admin).status_code == 404

    logs = client.get(f"{API}/audit-logs?entity_type=nearby_place&entity_id={rid}", headers=ctx.admin).json()
    assert [e["action"] for e in logs["items"]] == ["delete", "create"]

    link(client, ctx, related_village_id=ctx.b, relation_type="borders")
    assert client.delete(f"{API}/villages/{ctx.b}", headers=ctx.admin).status_code == 204
    assert client.get(ctx.url, headers=ctx.viewer).json() == []  # relations pointing to B went with it
