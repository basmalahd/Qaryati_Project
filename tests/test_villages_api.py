from app.models.village_name import VillageName

API = "/api/v1"


def make_gov(client, admin, name_ar="قلقيلية", name_en="Qalqilya"):
    r = client.post(f"{API}/governorates", json={"name_ar": name_ar, "name_en": name_en}, headers=admin)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def payload(gov_id, slug="jinsafut", name_ar="جينصافوط", name_en="Jinsafut", **extra):
    return {"slug": slug, "name_ar": name_ar, "name_en": name_en, "governorate_id": gov_id, **extra}


def make_village(client, headers, gov_id, **kw):
    r = client.post(f"{API}/villages", json=payload(gov_id, **kw), headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def test_requires_authentication(client):
    assert client.get(f"{API}/villages").status_code == 401
    assert client.get(f"{API}/governorates").status_code == 401


def test_create_permissions_and_validation(client, auth_headers):
    admin, editor, viewer = auth_headers("admin"), auth_headers("editor"), auth_headers("viewer")
    gov = make_gov(client, admin)

    assert client.post(f"{API}/villages", json=payload(gov), headers=viewer).status_code == 403

    r = client.post(f"{API}/villages", json=payload(gov, latitude=32.19, longitude=35.0), headers=editor)
    assert r.status_code == 201
    body = r.json()
    assert body["governorate"]["name_ar"] == "قلقيلية"
    assert body["names"] == []

    dup = client.post(f"{API}/villages", json=payload(gov), headers=editor)
    assert dup.status_code == 409 and dup.json()["code"] == "CONFLICT"

    bad_gov = client.post(f"{API}/villages", json=payload(999, slug="x"), headers=editor)
    assert bad_gov.status_code == 422 and bad_gov.json()["code"] == "UNPROCESSABLE"

    bad_slug = client.post(f"{API}/villages", json=payload(gov, slug="Bad Slug"), headers=editor)
    assert bad_slug.status_code == 422
    assert bad_slug.json()["details"][0]["field"] == "slug"

    lat_only = client.post(f"{API}/villages", json=payload(gov, slug="y", latitude=32.0), headers=editor)
    assert lat_only.status_code == 422


def test_list_pagination_filter_sort_search(client, auth_headers, session_factory):
    admin, editor = auth_headers("admin"), auth_headers("editor")
    g1 = make_gov(client, admin, "قلقيلية", "Qalqilya")
    g2 = make_gov(client, admin, "نابلس", "Nablus")
    make_village(client, editor, g1, slug="a-village", name_ar="أ قرية", name_en="Alpha")
    b = make_village(client, editor, g1, slug="b-village", name_ar="ب قرية", name_en="Beta")
    make_village(client, editor, g2, slug="c-village", name_ar="ج قرية", name_en="Gamma")

    page1 = client.get(f"{API}/villages?page_size=2", headers=editor).json()
    assert page1["total"] == 3 and page1["total_pages"] == 2 and len(page1["items"]) == 2
    page2 = client.get(f"{API}/villages?page_size=2&page=2", headers=editor).json()
    assert len(page2["items"]) == 1

    assert client.get(f"{API}/villages?governorate_id={g1}", headers=editor).json()["total"] == 2
    assert client.get(f"{API}/villages?q=alp", headers=editor).json()["total"] == 1  # case-insensitive
    assert client.get(f"{API}/villages?q=%25", headers=editor).json()["total"] == 0  # '%' is literal

    desc = client.get(f"{API}/villages?sort=name_en&order=desc", headers=editor).json()
    assert desc["items"][0]["name_en"] == "Gamma"

    assert client.get(f"{API}/villages?sort=password", headers=editor).status_code == 422
    assert client.get(f"{API}/villages?page_size=1000", headers=editor).status_code == 422

    with session_factory() as db:
        db.add(VillageName(village_id=b["id"], name="الحارة القديمة", language="ar",
                           name_type="historical"))
        db.commit()
    found = client.get(f"{API}/villages?q=الحارة", headers=editor).json()
    assert found["total"] == 1 and found["items"][0]["slug"] == "b-village"


def test_patch_is_partial_and_validated(client, auth_headers):
    admin, editor = auth_headers("admin"), auth_headers("editor")
    gov = make_gov(client, admin)
    v = make_village(client, editor, gov)
    make_village(client, editor, gov, slug="other", name_ar="أخرى", name_en="Other")

    r = client.patch(f"{API}/villages/{v['id']}", json={"name_en": "Jinsafut Village"}, headers=editor)
    assert r.status_code == 200
    assert r.json()["name_en"] == "Jinsafut Village" and r.json()["slug"] == "jinsafut"

    assert client.patch(f"{API}/villages/{v['id']}", json={"slug": "other"}, headers=editor).status_code == 409
    assert client.patch(f"{API}/villages/{v['id']}", json={"latitude": 32.0}, headers=editor).status_code == 422
    nul = client.patch(f"{API}/villages/{v['id']}", json={"name_ar": None}, headers=editor)
    assert nul.status_code == 422 and nul.json()["details"][0]["field"] == "name_ar"
    assert client.patch(f"{API}/villages/9999", json={"name_en": "x"}, headers=editor).status_code == 404


def test_delete_is_admin_only(client, auth_headers):
    admin, editor = auth_headers("admin"), auth_headers("editor")
    v = make_village(client, editor, make_gov(client, admin))
    assert client.delete(f"{API}/villages/{v['id']}", headers=editor).status_code == 403
    assert client.delete(f"{API}/villages/{v['id']}", headers=admin).status_code == 204
    assert client.get(f"{API}/villages/{v['id']}", headers=admin).status_code == 404


def test_governorate_permissions(client, auth_headers):
    admin, editor, viewer = auth_headers("admin"), auth_headers("editor"), auth_headers("viewer")
    body = {"name_ar": "جنين", "name_en": "Jenin"}
    assert client.post(f"{API}/governorates", json=body, headers=editor).status_code == 403
    assert client.post(f"{API}/governorates", json=body, headers=admin).status_code == 201
    assert client.post(f"{API}/governorates", json=body, headers=admin).status_code == 409
    assert len(client.get(f"{API}/governorates", headers=viewer).json()) == 1


def test_audit_trail_records_who_and_what(client, auth_headers):
    admin, editor, viewer = auth_headers("admin"), auth_headers("editor"), auth_headers("viewer")
    editor_id = client.get(f"{API}/users/me", headers=editor).json()["id"]
    v = make_village(client, editor, make_gov(client, admin))
    vid = v["id"]

    client.patch(f"{API}/villages/{vid}", json={"name_en": "Jinsafut"}, headers=editor)  # no-op
    client.patch(f"{API}/villages/{vid}", json={"name_en": "Jinsafut Village"}, headers=editor)
    client.delete(f"{API}/villages/{vid}", headers=admin)

    logs = client.get(f"{API}/audit-logs?entity_type=village&entity_id={vid}", headers=admin).json()
    assert logs["total"] == 3  # the no-op PATCH wrote nothing
    assert [e["action"] for e in logs["items"]] == ["delete", "update", "create"]
    create, update = logs["items"][2], logs["items"][1]
    assert create["user_id"] == editor_id and create["changes"]["after"]["slug"] == "jinsafut"
    assert update["changes"] == {"before": {"name_en": "Jinsafut"},
                                 "after": {"name_en": "Jinsafut Village"}}

    assert client.get(f"{API}/audit-logs", headers=viewer).status_code == 403


def test_stats_by_governorate_uses_native_sql(client, auth_headers):
    admin, editor = auth_headers("admin"), auth_headers("editor")
    g1 = make_gov(client, admin, "قلقيلية", "Qalqilya")
    make_gov(client, admin, "طولكرم", "Tulkarm")
    make_village(client, editor, g1, slug="one", name_ar="واحد", name_en="One")
    make_village(client, editor, g1, slug="two", name_ar="اثنان", name_en="Two")

    rows = client.get(f"{API}/stats/villages-by-governorate", headers=editor).json()
    assert [(r["name_en"], r["village_count"]) for r in rows] == [("Qalqilya", 2), ("Tulkarm", 0)]
