from types import SimpleNamespace

import pytest

from tests.helpers import API, make_gov, make_village


@pytest.fixture()
def ctx(client, auth_headers):
    admin, editor, verifier, viewer = (
        auth_headers(r) for r in ("admin", "editor", "verifier", "viewer")
    )
    village = make_village(client, editor, make_gov(client, admin))

    def make_source(title):
        r = client.post(f"{API}/sources", json={"title": title, "source_type": "census"}, headers=editor)
        assert r.status_code == 201, r.text
        return r.json()["id"]

    return SimpleNamespace(
        admin=admin, editor=editor, verifier=verifier, viewer=viewer,
        vid=village["id"], gov=village["governorate"]["id"],
        s1=make_source("PCBS 1997"), s2=make_source("Local council"),
        url=f"{API}/villages/{village['id']}/population",
    )


def add(client, ctx, population=1000, year=1997, source=None, headers=None):
    return client.post(
        ctx.url,
        json={"population": population, "reference_year": year, "source_id": source or ctx.s1},
        headers=headers or ctx.editor,
    )


def test_only_editors_and_admins_can_add(client, ctx):
    assert add(client, ctx, headers=ctx.viewer).status_code == 403
    assert add(client, ctx, headers=ctx.verifier).status_code == 403
    r = add(client, ctx)
    assert r.status_code == 201
    body = r.json()
    assert body["verification_status"] == "pending"
    assert body["source"]["title"] == "PCBS 1997"
    assert body["has_conflict"] is False


def test_validation_rules(client, ctx):
    assert add(client, ctx, population=-1).status_code == 422
    assert add(client, ctx, year=1700).status_code == 422
    future = add(client, ctx, year=2099)
    assert future.status_code == 422 and future.json()["details"][0]["field"] == "reference_year"

    unknown_source = add(client, ctx, source=9999)
    assert unknown_source.status_code == 422 and unknown_source.json()["code"] == "UNPROCESSABLE"

    missing_source = client.post(ctx.url, json={"population": 5, "reference_year": 2000}, headers=ctx.editor)
    assert missing_source.status_code == 422  # provenance is mandatory

    nowhere = client.post(f"{API}/villages/9999/population",
                          json={"population": 5, "reference_year": 2000, "source_id": ctx.s1},
                          headers=ctx.editor)
    assert nowhere.status_code == 404

    assert add(client, ctx).status_code == 201
    dup = add(client, ctx, population=999)
    assert dup.status_code == 409 and dup.json()["code"] == "CONFLICT"


def test_conflicting_sources_are_kept_and_flagged(client, ctx):
    add(client, ctx, 3000, 1997, ctx.s1)
    add(client, ctx, 2000, 2007, ctx.s1)
    second = add(client, ctx, 2200, 2007, ctx.s2)
    assert second.status_code == 201 and second.json()["has_conflict"] is True

    history = client.get(ctx.url, headers=ctx.viewer).json()
    assert [(r["reference_year"], r["has_conflict"]) for r in history] == [
        (1997, False), (2007, True), (2007, True),
    ]

    # same value from a second source is agreement, not a conflict
    agree = add(client, ctx, 3000, 1997, ctx.s2)
    assert agree.json()["has_conflict"] is False


def test_history_filters_and_ordering(client, ctx):
    add(client, ctx, 3000, 2007)
    add(client, ctx, 2000, 1997)
    add(client, ctx, 2500, 2017)
    years = lambda q: [r["reference_year"] for r in client.get(f"{ctx.url}{q}", headers=ctx.viewer).json()]
    assert years("") == [1997, 2007, 2017]
    assert years("?from_year=2000&to_year=2010") == [2007]
    assert years("?verification_status=verified") == []
    assert client.get(f"{ctx.url}?from_year=2010&to_year=2000", headers=ctx.viewer).status_code == 422
    assert client.get(f"{ctx.url}?verification_status=maybe", headers=ctx.viewer).status_code == 422


def test_verification_workflow_and_locking(client, ctx):
    rid = add(client, ctx).json()["id"]
    status_url = f"{ctx.url}/{rid}/status"

    assert client.patch(status_url, json={"status": "verified"}, headers=ctx.editor).status_code == 403
    assert client.patch(status_url, json={"status": "verified"}, headers=ctx.viewer).status_code == 403
    assert client.patch(status_url, json={"status": "approved"}, headers=ctx.verifier).status_code == 422

    ok = client.patch(status_url, json={"status": "verified"}, headers=ctx.verifier)
    assert ok.status_code == 200 and ok.json()["verification_status"] == "verified"

    locked = client.patch(f"{ctx.url}/{rid}", json={"population": 1234}, headers=ctx.editor)
    assert locked.status_code == 409

    client.patch(status_url, json={"status": "disputed"}, headers=ctx.verifier)
    edited = client.patch(f"{ctx.url}/{rid}", json={"population": 1234}, headers=ctx.editor)
    assert edited.status_code == 200
    assert edited.json()["population"] == 1234
    assert edited.json()["verification_status"] == "pending"  # edits need a fresh review


def test_update_rules(client, ctx):
    r1 = add(client, ctx, 1000, 1997, ctx.s1).json()["id"]
    add(client, ctx, 1100, 2007, ctx.s1)

    moved = client.patch(f"{ctx.url}/{r1}", json={"reference_year": 2007}, headers=ctx.editor)
    assert moved.status_code == 409  # would duplicate (village, 2007, source 1)
    assert client.patch(f"{ctx.url}/{r1}", json={"source_id": 9999}, headers=ctx.editor).status_code == 422
    assert client.patch(f"{ctx.url}/{r1}", json={"population": None}, headers=ctx.editor).status_code == 422
    assert client.patch(f"{ctx.url}/9999", json={"population": 1}, headers=ctx.editor).status_code == 404

    other = make_village(client, ctx.editor, ctx.gov, slug="other", name_ar="أخرى", name_en="Other")
    wrong_village = client.patch(f"{API}/villages/{other['id']}/population/{r1}",
                                 json={"population": 1}, headers=ctx.editor)
    assert wrong_village.status_code == 404


def test_delete_is_admin_only_and_audited(client, ctx):
    rid = add(client, ctx).json()["id"]
    client.patch(f"{ctx.url}/{rid}/status", json={"status": "verified"}, headers=ctx.verifier)

    assert client.delete(f"{ctx.url}/{rid}", headers=ctx.editor).status_code == 403
    assert client.delete(f"{ctx.url}/{rid}", headers=ctx.admin).status_code == 204
    assert client.get(ctx.url, headers=ctx.viewer).json() == []

    logs = client.get(f"{API}/audit-logs?entity_type=population_record&entity_id={rid}",
                      headers=ctx.admin).json()
    assert [e["action"] for e in logs["items"]] == ["delete", "update", "create"]
    assert logs["items"][1]["changes"] == {"before": {"verification_status": "pending"},
                                           "after": {"verification_status": "verified"}}
    assert logs["items"][0]["changes"]["before"]["population"] == 1000
