import httpx
import pytest

from app.core.cache import TTLCache
from app.core.config import settings
from app.integrations.geocoding import (
    GeocodingBadResponseError, GeocodingUnavailableError, GeoLocation, build_geocoder,
)
from app.integrations.geocoding.caching import CachingGeocoder
from app.integrations.geocoding.nominatim import NominatimGeocoder

OK_BODY = [
    {"lat": "32.19", "lon": "35.03", "display_name": "Jinsafut, Qalqilya"},
    {"lat": "bad", "lon": "35.0", "display_name": "broken item"},
    {"lat": "123", "lon": "35.0", "display_name": "impossible latitude"},
]


class FakeClock:
    """Controls time: sleeping advances it, so throttling can be tested instantly."""

    def __init__(self):
        self.now = 0.0
        self.sleeps: list[float] = []

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


def make_provider(handler, clock=None, **kw):
    clock = clock or FakeClock()
    client = httpx.Client(base_url="https://geo.test", transport=httpx.MockTransport(handler))
    kw.setdefault("min_interval", 0)
    return NominatimGeocoder(client, sleep=clock.sleep, clock=clock, **kw), clock


def test_success_sends_expected_request_and_skips_bad_items():
    seen = {}

    def handler(request):
        seen["params"] = dict(request.url.params)
        return httpx.Response(200, json=OK_BODY)

    provider, _ = make_provider(handler)
    results = provider.search("Jinsafut, Qalqilya", limit=3, country_code="ps")

    assert results == [GeoLocation(32.19, 35.03, "Jinsafut, Qalqilya")]
    assert seen["params"] == {"q": "Jinsafut, Qalqilya", "format": "jsonv2", "limit": "3",
                              "countrycodes": "ps"}


def test_retries_server_errors_then_succeeds():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(503) if len(calls) == 1 else httpx.Response(200, json=OK_BODY)

    provider, clock = make_provider(handler)
    assert len(provider.search("x")) == 1
    assert len(calls) == 2
    assert clock.sleeps == [0.5]  # one backoff between the two attempts


def test_gives_up_after_max_retries_with_exponential_backoff():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(500)

    provider, clock = make_provider(handler, max_retries=2)
    with pytest.raises(GeocodingUnavailableError):
        provider.search("x")
    assert len(calls) == 3
    assert clock.sleeps == [0.5, 1.0]


def test_timeouts_are_retried_then_reported_as_unavailable():
    calls = []

    def handler(request):
        calls.append(1)
        raise httpx.ReadTimeout("slow", request=request)

    provider, _ = make_provider(handler, max_retries=1)
    with pytest.raises(GeocodingUnavailableError):
        provider.search("x")
    assert len(calls) == 2


def test_rate_limit_response_honours_retry_after():
    calls = []

    def handler(request):
        calls.append(1)
        if len(calls) == 1:
            return httpx.Response(429, headers={"Retry-After": "2"})
        return httpx.Response(200, json=OK_BODY)

    provider, clock = make_provider(handler)
    provider.search("x")
    assert clock.sleeps == [2.0]


def test_client_errors_are_not_retried():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(400)

    provider, _ = make_provider(handler)
    with pytest.raises(GeocodingBadResponseError):
        provider.search("x")
    assert len(calls) == 1


@pytest.mark.parametrize("response", [
    httpx.Response(200, content=b"<html>not json</html>"),
    httpx.Response(200, json={"error": "something"}),
])
def test_unusable_payloads_are_bad_responses(response):
    provider, _ = make_provider(lambda request: response)
    with pytest.raises(GeocodingBadResponseError):
        provider.search("x")


def test_calls_are_spaced_by_min_interval():
    provider, clock = make_provider(lambda r: httpx.Response(200, json=[]), min_interval=1.0)
    provider.search("a")
    assert clock.sleeps == []  # first call goes straight through
    provider.search("b")
    assert clock.sleeps == [1.0]  # second call had to wait for the provider's 1 req/s limit


class CountingProvider:
    def __init__(self, results=None, fail_first=False):
        self.calls = 0
        self.results = results if results is not None else [GeoLocation(1.0, 2.0, "place")]
        self.fail_first = fail_first

    def search(self, query, *, limit=5, country_code=None):
        self.calls += 1
        if self.fail_first and self.calls == 1:
            raise GeocodingUnavailableError("down")
        return list(self.results)


def make_cache(inner):
    return CachingGeocoder(inner, TTLCache(), ttl=100, empty_ttl=10)


def test_cache_normalizes_queries_and_avoids_second_call():
    inner = CountingProvider()
    geocoder = make_cache(inner)
    first = geocoder.search("Jinsafut,  Qalqilya", country_code="ps")
    second = geocoder.search("  jinsafut, QALQILYA", country_code="ps")
    assert first == second and inner.calls == 1
    geocoder.search("jinsafut, qalqilya", country_code="ps", limit=1)  # different limit = new key
    assert inner.calls == 2


def test_empty_results_are_cached_but_failures_are_not():
    empty = CountingProvider(results=[])
    geocoder = make_cache(empty)
    geocoder.search("nowhere")
    geocoder.search("nowhere")
    assert empty.calls == 1

    flaky = CountingProvider(fail_first=True)
    geocoder = make_cache(flaky)
    with pytest.raises(GeocodingUnavailableError):
        geocoder.search("x")
    assert len(geocoder.search("x")) == 1  # recovered immediately: the failure wasn't cached
    assert flaky.calls == 2


def test_factory_builds_cached_nominatim_stack():
    geocoder = build_geocoder(settings)
    assert isinstance(geocoder, CachingGeocoder)
    client = geocoder._inner._client
    assert client.headers["user-agent"] == settings.geocoding_user_agent
    assert str(client.base_url).startswith(settings.geocoding_base_url)
