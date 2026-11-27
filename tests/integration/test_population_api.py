
from types import SimpleNamespace

import pytest

from tests.helpers import API, make_gov, make_village


@pytest.fixture()
def ctx(client, auth_headers):
    admin, editor, verifier, viewer = (
        auth_headers(role)
        for role in ("admin", "editor", "verifier", "viewer")
    )

    village = make_village(
        client,
        editor,
        make_gov(client, admin),
    )

    def make_source(title):
        response = client.post(
            f"{API}/sources",
            json={
                "title": title,
                "source_type": "census",
            },
            headers=editor,
        )
        assert response.status_code == 201, response.text
        return response.json()["id"]

    return SimpleNamespace(
        admin=admin,
        editor=editor,
        verifier=verifier,
        viewer=viewer,
        vid=village["id"],
        gov=village["governorate"]["id"],
        s1=make_source("PCBS 1997"),
        s2=make_source("Local council"),
        url=f"{API}/villages/{village['id']}/population",
    )


def add(
        client,
        ctx,
        population=1000,
        year=1997,
        source=None,
        headers=None,
):
    return client.post(
        ctx.url,
        json={
            "population": population,
            "reference_year": year,
            "source_id": source or ctx.s1,
        },
        headers=headers or ctx.editor,
    )


def test_only_editors_and_admins_can_add(client, ctx):
    assert add(client, ctx, headers=ctx.viewer).status_code == 403
    assert add(client, ctx, headers=ctx.verifier).status_code == 403

    response = add(client, ctx)
    assert response.status_code == 201

    body = response.json()
    assert body["verification_status"] == "pending"
    assert body["source"]["title"] == "PCBS 1997"
    assert body["has_conflict"] is False


def test_validation_rules(client, ctx):
    assert add(client, ctx, population=-1).status_code == 422
    assert add(client, ctx, year=1700).status_code == 422

    future = add(client, ctx, year=2099)
    assert future.status_code == 422
    assert (
            future.json()["details"][0]["field"]
            == "reference_year"
    )

    unknown_source = add(client, ctx, source=9999)
    assert unknown_source.status_code == 422
    assert unknown_source.json()["code"] == "UNPROCESSABLE"

    missing_source = client.post(
        ctx.url,
        json={
            "population": 5,
            "reference_year": 2000,
        },
        headers=ctx.editor,
    )
    assert missing_source.status_code == 422

    nowhere = client.post(
        f"{API}/villages/9999/population",
        json={
            "population": 5,
            "reference_year": 2000,
            "source_id": ctx.s1,
        },
        headers=ctx.editor,
    )
    assert nowhere.status_code == 404

    assert add(client, ctx).status_code == 201

    duplicate = add(client, ctx, population=999)
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "CONFLICT"


def test_conflicting_sources_are_kept_and_flagged(client, ctx):
    add(client, ctx, 3000, 1997, ctx.s1)
    add(client, ctx, 2000, 2007, ctx.s1)

    second = add(client, ctx, 2200, 2007, ctx.s2)
    assert second.status_code == 201
    assert second.json()["has_conflict"] is True

    history = client.get(
        ctx.url,
        headers=ctx.viewer,
    ).json()

    assert [
               (record["reference_year"], record["has_conflict"])
               for record in history
           ] == [
               (1997, False),
               (2007, True),
               (2007, True),
           ]

    # Agreement between sources is not a conflict.
    agreement = add(client, ctx, 3000, 1997, ctx.s2)
    assert agreement.json()["has_conflict"] is False


def test_history_filters_and_ordering(client, ctx):
    add(client, ctx, 3000, 2007)
    add(client, ctx, 2000, 1997)
    add(client, ctx, 2500, 2017)


    def years(query):
        response = client.get(
            f"{ctx.url}{query}",
            headers=ctx.viewer,
        )
        return [
            record["reference_year"]
            for record in response.json()
        ]


    assert years("") == [1997, 2007, 2017]
    assert years("?from_year=2000&to_year=2010") == [2007]
    assert years("?verification_status=verified") == []

    invalid_range = client.get(
        f"{ctx.url}?from_year=2010&to_year=2000",
        headers=ctx.viewer,
    )
    assert invalid_range.status_code == 422

    invalid_status = client.get(
        f"{ctx.url}?verification_status=maybe",
        headers=ctx.viewer,
    )
    assert invalid_status.status_code == 422


def test_verification_workflow_and_locking(client, ctx):
    record_id = add(client, ctx).json()["id"]
    status_url = f"{ctx.url}/{record_id}/status"

    assert client.patch(
        status_url,
        json={"status": "verified"},
        headers=ctx.editor,
    ).status_code == 403

    assert client.patch(
        status_url,
        json={"status": "verified"},
        headers=ctx.viewer,
    ).status_code == 403

    assert client.patch(
        status_url,
        json={"status": "approved"},
        headers=ctx.verifier,
    ).status_code == 422

    verified = client.patch(
        status_url,
        json={"status": "verified"},
        headers=ctx.verifier,
    )
    assert verified.status_code == 200
    assert verified.json()["verification_status"] == "verified"

    locked = client.patch(
        f"{ctx.url}/{record_id}",
        json={"population": 1234},
        headers=ctx.editor,
    )
    assert locked.status_code == 409

    client.patch(
        status_url,
        json={"status": "disputed"},
        headers=ctx.verifier,
    )

    edited = client.patch(
        f"{ctx.url}/{record_id}",
        json={"population": 1234},
        headers=ctx.editor,
    )

    assert edited.status_code == 200
    assert edited.json()["population"] == 1234
    assert edited.json()["verification_status"] == "pending"


def test_update_rules(client, ctx):
    record_id = add(
        client,
        ctx,
        1000,
        1997,
        ctx.s1,
    ).json()["id"]

    add(client, ctx, 1100, 2007, ctx.s1)

    moved = client.patch(
        f"{ctx.url}/{record_id}",
        json={"reference_year": 2007},
        headers=ctx.editor,
    )
    assert moved.status_code == 409

    assert client.patch(
        f"{ctx.url}/{record_id}",
        json={"source_id": 9999},
        headers=ctx.editor,
    ).status_code == 422

    assert client.patch(
        f"{ctx.url}/{record_id}",
        json={"population": None},
        headers=ctx.editor,
    ).status_code == 422

    assert client.patch(
        f"{ctx.url}/9999",
        json={"population": 1},
        headers=ctx.editor,
    ).status_code == 404

    other_village = make_village(
        client,
        ctx.editor,
        ctx.gov,
        slug="other",
        name_ar="أخرى",
        name_en="Other",
    )

    wrong_village = client.patch(
        f"{API}/villages/{other_village['id']}/population/{record_id}",
        json={"population": 1},
        headers=ctx.editor,
    )
    assert wrong_village.status_code == 404


def test_delete_is_admin_only_and_audited(client, ctx):
    record_id = add(client, ctx).json()["id"]

    client.patch(
        f"{ctx.url}/{record_id}/status",
        json={"status": "verified"},
        headers=ctx.verifier,
    )

    assert client.delete(
        f"{ctx.url}/{record_id}",
        headers=ctx.editor,
    ).status_code == 403

    assert client.delete(
        f"{ctx.url}/{record_id}",
        headers=ctx.admin,
    ).status_code == 204

    assert client.get(
        ctx.url,
        headers=ctx.viewer,
    ).json() == []

    logs = client.get(
        f"{API}/audit-logs"
        f"?entity_type=population_record&entity_id={record_id}",
        headers=ctx.admin,
    ).json()

    assert [
        entry["action"]
        for entry in logs["items"]
    ] == [
        "delete",
        "update",
        "create",
    ]

    assert logs["items"][1]["changes"] == {
        "before": {
            "verification_status": "pending",
        },
        "after": {
            "verification_status": "verified",
        },
    }

    assert (
        logs["items"][0]["changes"]["before"]["population"]
        == 1000
    )


# ---- native SQL: latest population per village ---------------------------------------


def _second_village(
    client,
    ctx,
    slug="other",
    name_ar="أخرى",
    name_en="Other",
):
    from tests.helpers import make_village

    return make_village(
        client,
        ctx.editor,
        ctx.gov,
        slug=slug,
        name_ar=name_ar,
        name_en=name_en,
    )


def _add_to(client, ctx, village_id, population, year, source=None):
    response = client.post(
        f"{API}/villages/{village_id}/population",
        json={
            "population": population,
            "reference_year": year,
            "source_id": source or ctx.s1,
        },
        headers=ctx.editor,
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_latest_population_picks_newest_year_per_village(client, ctx):
    add(client, ctx, population=900, year=1997)
    add(client, ctx, population=1500, year=2017)

    other = _second_village(client, ctx)
    _add_to(client, ctx, other["id"], 3000, 2007)

    rows = client.get(
        f"{API}/stats/latest-population",
        headers=ctx.viewer,
    ).json()

    # Biggest first, exactly one row per village, newest year wins.
    assert [
        (r["village_id"], r["population"], r["reference_year"])
        for r in rows
    ] == [
        (other["id"], 3000, 2007),
        (ctx.vid, 1500, 2017),
    ]


def test_latest_population_prefers_verified_and_ignores_disputed(
    client,
    ctx,
):
    pending = add(
        client,
        ctx,
        population=1000,
        year=2017,
    ).json()

    verified = add(
        client,
        ctx,
        population=1100,
        year=2017,
        source=ctx.s2,
    ).json()

    client.patch(
        f"{ctx.url}/{verified['id']}/status",
        json={"status": "verified"},
        headers=ctx.verifier,
    )

    other = _second_village(client, ctx)
    bad = _add_to(client, ctx, other["id"], 9999, 2020)

    client.patch(
        f"{API}/villages/{other['id']}/population/{bad['id']}/status",
        json={"status": "disputed"},
        headers=ctx.verifier,
    )

    _add_to(client, ctx, other["id"], 500, 2010)

    rows = {
        r["village_id"]: r
        for r in client.get(
            f"{API}/stats/latest-population",
            headers=ctx.viewer,
        ).json()
    }

    assert (
        rows[ctx.vid]["population"] == 1100
        and rows[ctx.vid]["verification_status"] == "verified"
    )

    assert rows[other["id"]]["population"] == 500

    # The disputed 2020 record is skipped.
    assert pending["id"] != verified["id"]


def test_latest_population_filters_limits_and_skips_villages_without_data(
    client,
    ctx,
):
    add(client, ctx, population=1000, year=2017)

    other_gov = make_gov(
        client,
        ctx.admin,
        "طولكرم",
        "Tulkarm",
    )

    from tests.helpers import make_village

    far = make_village(
        client,
        ctx.editor,
        other_gov,
        slug="far",
        name_ar="بعيدة",
        name_en="Far",
    )

    _add_to(client, ctx, far["id"], 70, 2017)

    make_village(
        client,
        ctx.editor,
        ctx.gov,
        slug="empty",
        name_ar="فارغة",
        name_en="Empty",
    )

    # No population records for this village.

    by_gov = client.get(
        f"{API}/stats/latest-population?governorate_id={ctx.gov}",
        headers=ctx.viewer,
    ).json()

    # Filtered by governorate, and the empty village is not listed.
    assert [r["village_id"] for r in by_gov] == [ctx.vid]

    limited = client.get(
        f"{API}/stats/latest-population?limit=1",
        headers=ctx.viewer,
    ).json()

    assert len(limited) == 1
    assert limited[0]["population"] == 1000

    assert client.get(
        f"{API}/stats/latest-population?limit=0",
        headers=ctx.viewer,
    ).status_code == 422

    assert client.get(
        f"{API}/stats/latest-population",
    ).status_code == 401