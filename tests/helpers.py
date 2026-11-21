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


def make_source(client, headers, title="PCBS 1997", source_type="census"):
    r = client.post(f"{API}/sources", json={"title": title, "source_type": source_type}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]
