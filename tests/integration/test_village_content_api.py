
from datetime import date
from types import SimpleNamespace
from typing import get_args

import pytest

from app.models import content as m
from app.schemas import content as s
from tests.helpers import API, make_gov, make_source, make_village


# Shared configuration for the five village-content resources.
RESOURCES = {
    "events": dict(
        entity="historical_event",
        required="title",
        create={"title": "Village founded", "year": 1850},
        create2={"title": "Earthquake", "date_note": "1927"},
        enum=None,
        flt=None,
        unique=False,
    ),
    "landmarks": dict(
        entity="landmark",
        required="name_ar",
        create={"name_ar": "عين الماء", "category": "spring"},
        create2={"name_ar": "المقام", "category": "religious_site"},
        enum=("category", "castle"),
        flt=("category", "spring"),
        unique=True,
    ),
    "heritage": dict(
        entity="heritage_item",
        required="name",
        create={"name": "Embroidery", "category": "craft"},
        create2={"name": "Maqluba", "category": "food"},
        enum=("category", "music"),
        flt=("category", "craft"),
        unique=True,
    ),
    "economy": dict(
        entity="economic_item",
        required="name",
        create={"name": "Olives", "category": "crop"},
        create2={"name": "Stone cutting", "category": "industry"},
        enum=("category", "magic"),
        flt=("category", "crop"),
        unique=True,
    ),
    "facilities": dict(
        entity="facility",
        required="name",
        create={"name": "Boys School", "facility_type": "school"},
        create2={"name": "Health Clinic", "facility_type": "clinic"},
        enum=("facility_type", "spaceport"),
        flt=("facility_type", "school"),
        unique=True,
    ),
}

NAMES = list(RESOURCES)


@pytest.fixture()
def ctx(client, auth_headers):
    admin = auth_headers("admin")
    editor = auth_headers("editor")
    viewer = auth_headers("viewer")

    gov = make_gov(client, admin)
    village = make_village(client, editor, gov)

    other = make_village(
        client,
        editor,
        gov,
        slug="other",
        name_ar="أخرى",
        name_en="Other",
    )

    return SimpleNamespace(
        admin=admin,
        editor=editor,
        viewer=viewer,
        vid=village["id"],
        other=other["id"],
        sid=make_source(client, editor),
    )


def url(ctx, name, village=None):
    return f"{API}/villages/{village or ctx.vid}/{name}"


def test_schema_literals_match_database_constraints():
    assert get_args(s.LandmarkCategory) == m.LANDMARK_CATEGORIES
    assert get_args(s.HeritageCategory) == m.HERITAGE_CATEGORIES
    assert get_args(s.EconomicCategory) == m.ECONOMIC_CATEGORIES
    assert get_args(s.FacilityType) == m.FACILITY_TYPES


def test_openapi_documents_every_resource(client):
    paths = client.get("/openapi.json").json()["paths"]

    for name in NAMES:
        assert f"/api/v1/villages/{{village_id}}/{name}" in paths
        assert f"/api/v1/villages/{{village_id}}/{name}/{{item_id}}" in paths


@pytest.mark.parametrize("name", NAMES)
def test_permissions_create_and_list(client, ctx, name):
    cfg = RESOURCES[name]

    assert client.post(
        url(ctx, name),
        json=cfg["create"],
        headers=ctx.viewer,
    ).status_code == 403

    assert client.get(url(ctx, name)).status_code == 401

    created = client.post(
        url(ctx, name),
        json=cfg["create"],
        headers=ctx.editor,
    )

    assert created.status_code == 201, created.text

    body = created.json()

    assert body["village_id"] == ctx.vid
    assert body["source"] is None

    for key, value in cfg["create"].items():
        assert body[key] == value

    listed = client.get(
        url(ctx, name),
        headers=ctx.viewer,
    ).json()

    assert [item["id"] for item in listed] == [body["id"]]

    assert client.get(
        url(ctx, name, ctx.other),
        headers=ctx.viewer,
    ).json() == []


@pytest.mark.parametrize("name", NAMES)
def test_sources_and_unknown_village(client, ctx, name):
    cfg = RESOURCES[name]

    with_source = client.post(
        url(ctx, name),
        json={**cfg["create"], "source_id": ctx.sid},
        headers=ctx.editor,
    )

    assert with_source.status_code == 201
    assert with_source.json()["source"]["title"] == "PCBS 1997"

    assert client.post(
        url(ctx, name),
        json={**cfg["create2"], "source_id": 9999},
        headers=ctx.editor,
    ).status_code == 422

    assert client.post(
        url(ctx, name, 9999),
        json=cfg["create"],
        headers=ctx.editor,
    ).status_code == 404

    assert client.get(
        url(ctx, name, 9999),
        headers=ctx.viewer,
    ).status_code == 404


@pytest.mark.parametrize("name", NAMES)
def test_validation_and_duplicates(client, ctx, name):
    cfg = RESOURCES[name]

    missing = {
        key: value
        for key, value in cfg["create"].items()
        if key != cfg["required"]
    }

    assert client.post(
        url(ctx, name),
        json=missing,
        headers=ctx.editor,
    ).status_code == 422

    if cfg["enum"]:
        field, bad = cfg["enum"]

        assert client.post(
            url(ctx, name),
            json={**cfg["create"], field: bad},
            headers=ctx.editor,
        ).status_code == 422

    assert client.post(
        url(ctx, name),
        json=cfg["create"],
        headers=ctx.editor,
    ).status_code == 201

    again = client.post(
        url(ctx, name),
        json=cfg["create"],
        headers=ctx.editor,
    )

    assert again.status_code == (
        409 if cfg["unique"] else 201
    )


@pytest.mark.parametrize("name", NAMES)
def test_update_rules(client, ctx, name):
    cfg = RESOURCES[name]

    item = client.post(
        url(ctx, name),
        json=cfg["create"],
        headers=ctx.editor,
    ).json()

    second = client.post(
        url(ctx, name),
        json=cfg["create2"],
        headers=ctx.editor,
    ).json()

    target = f"{url(ctx, name)}/{item['id']}"

    ok = client.patch(
        target,
        json={"description": "Updated text"},
        headers=ctx.editor,
    )

    assert ok.status_code == 200
    assert ok.json()["description"] == "Updated text"

    for key, value in cfg["create"].items():
        assert ok.json()[key] == value

    assert client.patch(
        target,
        json={cfg["required"]: None},
        headers=ctx.editor,
    ).status_code == 422

    assert client.patch(
        target,
        json={"source_id": 9999},
        headers=ctx.editor,
    ).status_code == 422

    assert client.patch(
        target,
        json={"description": "x"},
        headers=ctx.viewer,
    ).status_code == 403

    assert client.patch(
        f"{url(ctx, name)}/9999",
        json={"description": "x"},
        headers=ctx.editor,
    ).status_code == 404

    other_village = (
        f"{url(ctx, name, ctx.other)}/{item['id']}"
    )

    assert client.patch(
        other_village,
        json={"description": "x"},
        headers=ctx.editor,
    ).status_code == 404

    if cfg["unique"]:
        clash = {
            key: value
            for key, value in cfg["create"].items()
            if key in ("name", "name_ar")
        }

        clash_target = (
            f"{url(ctx, name)}/{second['id']}"
        )

        assert client.patch(
            clash_target,
            json=clash,
            headers=ctx.editor,
        ).status_code in (409, 200)

        if (
                "category" in cfg["create"]
                or "facility_type" in cfg["create"]
        ):
            same_type = dict(cfg["create"])

            assert client.patch(
                clash_target,
                json=same_type,
                headers=ctx.editor,
            ).status_code == 409


@pytest.mark.parametrize("name", NAMES)
def test_delete_is_admin_only_and_audited(client, ctx, name):
    cfg = RESOURCES[name]

    item = client.post(
        url(ctx, name),
        json=cfg["create"],
        headers=ctx.editor,
    ).json()

    target = f"{url(ctx, name)}/{item['id']}"

    client.patch(
        target,
        json={"description": "changed"},
        headers=ctx.editor,
    )

    assert client.delete(
        target,
        headers=ctx.editor,
    ).status_code == 403

    assert client.delete(
        target,
        headers=ctx.admin,
    ).status_code == 204

    assert client.delete(
        target,
        headers=ctx.admin,
    ).status_code == 404

    logs = client.get(
        f"{API}/audit-logs"
        f"?entity_type={cfg['entity']}"
        f"&entity_id={item['id']}",
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

    assert logs["items"][1]["changes"]["after"] == {
        "description": "changed"
    }


@pytest.mark.parametrize(
    "name",
    [name for name in NAMES if RESOURCES[name]["flt"]],
)
def test_category_filter(client, ctx, name):
    cfg = RESOURCES[name]

    client.post(
        url(ctx, name),
        json=cfg["create"],
        headers=ctx.editor,
    )

    client.post(
        url(ctx, name),
        json=cfg["create2"],
        headers=ctx.editor,
    )

    field, value = cfg["flt"]

    assert len(
        client.get(
            url(ctx, name),
            headers=ctx.viewer,
        ).json()
    ) == 2

    filtered = client.get(
        f"{url(ctx, name)}?{field}={value}",
        headers=ctx.viewer,
    ).json()

    assert len(filtered) == 1
    assert filtered[0][field] == value

    assert client.get(
        f"{url(ctx, name)}?{field}=nonsense",
        headers=ctx.viewer,
    ).status_code == 422


def test_deleting_a_village_removes_all_its_content(
        client,
        ctx,
        session_factory,
):
    from sqlalchemy import func, select

    for name in NAMES:
        client.post(
            url(ctx, name),
            json=RESOURCES[name]["create"],
            headers=ctx.editor,
        )

    assert client.delete(
        f"{API}/villages/{ctx.vid}",
        headers=ctx.admin,
    ).status_code == 204

    with session_factory() as db:
        for model in (
                m.HistoricalEvent,
                m.Landmark,
                m.HeritageItem,
                m.EconomicItem,
                m.Facility,
        ):
            assert db.scalar(
                select(func.count()).select_from(model)
            ) == 0


# Resource-specific rules

def test_event_needs_a_time_and_cannot_be_in_the_future(
        client,
        ctx,
):
    base = {"title": "Something happened"}

    neither = client.post(
        url(ctx, "events"),
        json=base,
        headers=ctx.editor,
    )

    assert neither.status_code == 422
    assert neither.json()["details"][0]["field"] == "body"

    assert client.post(
        url(ctx, "events"),
        json={
            **base,
            "year": date.today().year + 1,
        },
        headers=ctx.editor,
    ).status_code == 422

    assert client.post(
        url(ctx, "events"),
        json={**base, "date_note": "  "},
        headers=ctx.editor,
    ).status_code == 422

    assert client.post(
        url(ctx, "events"),
        json={**base, "year": -1200},
        headers=ctx.editor,
    ).status_code == 201

    item = client.post(
        url(ctx, "events"),
        json={
            "title": "Dated",
            "year": 1900,
        },
        headers=ctx.editor,
    ).json()

    clear_year = client.patch(
        f"{url(ctx, 'events')}/{item['id']}",
        json={"year": None},
        headers=ctx.editor,
    )

    assert clear_year.status_code == 422


def test_timeline_order_and_year_filter(client, ctx):

    events = (
        {"title": "C", "year": 1948},
        {"title": "A", "year": 1850},
        {"title": "Undated", "date_note": "Ottoman period"},
        {"title": "B", "year": 1917},
    )

    for body in events:
        client.post(
            url(ctx, "events"),
            json=body,
            headers=ctx.editor,
        )

    def titles(q=""):
        response = client.get(
            f"{url(ctx, 'events')}{q}",
            headers=ctx.viewer,
        )

        return [
            event["title"]
            for event in response.json()
        ]

    assert titles() == ["A", "B", "C", "Undated"]
=======
    for body in ({"title": "C", "year": 1948}, {"title": "A", "year": 1850},
                 {"title": "Undated", "date_note": "Ottoman period"}, {"title": "B", "year": 1917}):
        client.post(url(ctx, "events"), json=body, headers=ctx.editor)

    def titles(q=""):
        return [e["title"] for e in client.get(f"{url(ctx, 'events')}{q}", headers=ctx.viewer).json()]
    assert titles() == ["A", "B", "C", "Undated"]  # chronological, undated last

    assert titles("?from_year=1900&to_year=1930") == ["B"]
    assert titles("?from_year=1900") == ["B", "C"]

    assert client.get(
        f"{url(ctx, 'events')}?from_year=1950&to_year=1900",
        headers=ctx.viewer,
    ).status_code == 422


def test_landmark_coordinates_must_be_a_pair(client, ctx):
    base = {
        "name_ar": "عين",
        "category": "spring",
    }

    assert client.post(
        url(ctx, "landmarks"),
        json={**base, "latitude": 32.1},
        headers=ctx.editor,
    ).status_code == 422

    assert client.post(
        url(ctx, "landmarks"),
        json={
            **base,
            "latitude": 95,
            "longitude": 35,
        },
        headers=ctx.editor,
    ).status_code == 422

    ok = client.post(
        url(ctx, "landmarks"),
        json={
            **base,
            "latitude": 32.1,
            "longitude": 35.0,
        },
        headers=ctx.editor,
    )

    assert ok.status_code == 201

    target = (
        f"{url(ctx, 'landmarks')}/{ok.json()['id']}"
    )

    assert client.patch(
        target,
        json={"latitude": None},
        headers=ctx.editor,
    ).status_code == 422

    both = client.patch(
        target,
        json={
            "latitude": None,
            "longitude": None,
        },
        headers=ctx.editor,
    )

    assert both.status_code == 200
    assert both.json()["latitude"] is None


def test_same_name_in_different_categories_is_allowed(
        client,
        ctx,
):
    assert client.post(
        url(ctx, "economy"),
        json={
            "name": "Olives",
            "category": "crop",
        },
        headers=ctx.editor,
    ).status_code == 201

    assert client.post(
        url(ctx, "economy"),
        json={
            "name": "Olives",
            "category": "industry",
        },
        headers=ctx.editor,
    ).status_code == 201
