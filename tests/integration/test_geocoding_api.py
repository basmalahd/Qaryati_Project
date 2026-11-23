import pytest

from app.api.deps import get_geocoder
from app.integrations.geocoding import (
    GeocodingBadResponseError, GeocodingUnavailableError, GeoLocation,
)
from app.main import app
from tests.helpers import API, make_gov, make_village


class FakeGeocoder:
    def __init__(self, results=None, error=None):
        self.results = results or []
        self.error = error
        self.calls = []

    def search(self, query, *, limit=5, country_code=None):
        self.calls.append((query, limit, country_code))
        if self.error:
            raise self.error
        return self.results


@pytest.fixture()
def setup(client, auth_headers):
    admin, editor, viewer = auth_headers("admin"), auth_headers("editor"), auth_headers("viewer")
    gov = make_gov(client, admin)
    return admin, editor, viewer, gov


def use(fake):
    app.dependency_overrides[get_geocoder] = lambda: fake
    return fake


def test_requires_editor_or_admin(client, setup):
    admin, editor, viewer, gov = setup
    v = make_village(client, editor, gov)
    use(FakeGeocoder())
    assert client.get(f"{API}/villages/{v['id']}/location-suggestions").status_code == 401
    assert client.get(f"{API}/villages/{v['id']}/location-suggestions", headers=viewer).status_code == 403
    assert client.get(f"{API}/geocoding/search?q=jinsafut", headers=viewer).status_code == 403


def test_suggestions_for_village_without_coordinates(client, setup):
    admin, editor, viewer, gov = setup
    v = make_village(client, editor, gov)
    fake = use(FakeGeocoder([GeoLocation(32.19, 35.03, "Jinsafut, Qalqilya, Palestine")]))

    r = client.get(f"{API}/villages/{v['id']}/location-suggestions", headers=editor)
    assert r.status_code == 200
    body = r.json()
    assert body["query"] == "Jinsafut, Qalqilya"
    assert body["current_latitude"] is None
    assert body["candidates"] == [{"latitude": 32.19, "longitude": 35.03,
                                   "display_name": "Jinsafut, Qalqilya, Palestine",
                                   "distance_km": None}]
    assert fake.calls == [("Jinsafut, Qalqilya", 5, "ps")]


def test_suggestions_report_distance_from_current_coordinates_and_do_not_overwrite(client, setup):
    admin, editor, viewer, gov = setup
    v = make_village(client, editor, gov, latitude=32.0, longitude=35.0)
    use(FakeGeocoder([GeoLocation(33.0, 35.0, "far away")]))

    body = client.get(f"{API}/villages/{v['id']}/location-suggestions", headers=editor).json()
    assert abs(body["candidates"][0]["distance_km"] - 111.19) < 0.5

    after = client.get(f"{API}/villages/{v['id']}", headers=editor).json()
    assert (after["latitude"], after["longitude"]) == (32.0, 35.0)  # suggestion never writes


def test_unknown_village_is_404(client, setup):
    use(FakeGeocoder())
    assert client.get(f"{API}/villages/9999/location-suggestions", headers=setup[1]).status_code == 404


def test_provider_outage_becomes_503_not_a_crash(client, setup):
    admin, editor, viewer, gov = setup
    v = make_village(client, editor, gov)
    use(FakeGeocoder(error=GeocodingUnavailableError("timeout")))

    r = client.get(f"{API}/villages/{v['id']}/location-suggestions", headers=editor)
    assert r.status_code == 503
    body = r.json()
    assert body["code"] == "GEOCODING_UNAVAILABLE"
    assert set(body) == {"timestamp", "status", "code", "message", "details", "traceId"}
    assert "timeout" not in body["message"]  # internals are not leaked

    # the rest of the API keeps working
    assert client.get(f"{API}/villages/{v['id']}", headers=editor).status_code == 200


def test_unusable_provider_response_becomes_502(client, setup):
    use(FakeGeocoder(error=GeocodingBadResponseError("garbage")))
    r = client.get(f"{API}/geocoding/search?q=jinsafut", headers=setup[1])
    assert r.status_code == 502 and r.json()["code"] == "GEOCODING_BAD_RESPONSE"


def test_search_endpoint_validates_input(client, setup):
    editor = setup[1]
    fake = use(FakeGeocoder([GeoLocation(1.0, 2.0, "x")]))
    assert client.get(f"{API}/geocoding/search?q=a", headers=editor).status_code == 422
    assert client.get(f"{API}/geocoding/search?q=ab&limit=99", headers=editor).status_code == 422
    ok = client.get(f"{API}/geocoding/search?q=Nablus&limit=3", headers=editor)
    assert ok.status_code == 200 and len(ok.json()) == 1
    assert fake.calls == [("Nablus", 3, "ps")]
