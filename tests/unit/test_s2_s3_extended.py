"""Extended regression tests for Qaryati S2 (rate limiting) and S3 (JSON logging)."""
import json
import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.middleware import add_request_id_middleware
from app.core.rate_limit import (
    _allow,
    _enabled,
    _positive_int,
    _rule,
    add_rate_limit_middleware,
    clear_rate_limits,
)
from app.core.structured_logging import (
    JsonFormatter,
    add_access_log_middleware,
    configure_json_logging,
)


@pytest.fixture(autouse=True)
def reset_limits():
    clear_rate_limits()
    yield
    clear_rate_limits()


def make_app(*, rate=True, access=False):
    app = FastAPI()
    if access:
        add_access_log_middleware(app)
    if rate:
        add_rate_limit_middleware(app)
    add_request_id_middleware(app)

    @app.get('/hello')
    def hello():
        return {'ok': True}

    @app.post('/api/v1/auth/login')
    def login():
        return {'ok': True}

    @app.post('/api/v1/auth/register')
    def register():
        return {'ok': True}

    @app.get('/api/v1/auth/login-history')
    def history():
        return {'ok': True}

    return app


@pytest.mark.parametrize('value, expected', [
    ('true', True), ('TRUE', True), ('1', True),
    ('false', False), ('FALSE', False), ('0', False),
    ('no', False), ('off', False),
])
def test_enabled_flag(monkeypatch, value, expected):
    monkeypatch.setenv('RATE_LIMIT_ENABLED', value)
    assert _enabled() is expected


@pytest.mark.parametrize('bad', ['0', '-1', 'abc', '1.5', ''])
def test_invalid_rate_limit_configuration(monkeypatch, bad):
    monkeypatch.setenv('RATE_LIMIT_GENERAL_PER_MINUTE', bad)
    with pytest.raises(ValueError, match='positive integer'):
        _positive_int('RATE_LIMIT_GENERAL_PER_MINUTE', 120)


def test_default_limit(monkeypatch):
    monkeypatch.delenv('RATE_LIMIT_GENERAL_PER_MINUTE', raising=False)
    assert _positive_int('RATE_LIMIT_GENERAL_PER_MINUTE', 120) == 120


@pytest.mark.parametrize('path, bucket', [
    ('/api/v1/auth/login', 'login'),
    ('/api/v1/auth/login/', 'login'),
    ('/api/v1/auth/register', 'register'),
    ('/api/v1/auth/register/', 'register'),
    ('/api/v1/auth/login-history', 'general'),
    ('/hello', 'general'),
])
def test_route_bucket_is_exact(path, bucket):
    assert _rule(path)[0] == bucket


def test_special_auth_limits(monkeypatch):
    monkeypatch.setenv('RATE_LIMIT_GENERAL_PER_MINUTE', '100')
    monkeypatch.setenv('RATE_LIMIT_LOGIN_PER_MINUTE', '2')
    monkeypatch.setenv('RATE_LIMIT_REGISTER_PER_MINUTE', '1')
    assert _rule('/hello') == ('general', 100)
    assert _rule('/api/v1/auth/login') == ('login', 2)
    assert _rule('/api/v1/auth/register') == ('register', 1)


def test_first_request_allowed_and_second_rejected(monkeypatch):
    monkeypatch.setenv('RATE_LIMIT_ENABLED', 'true')
    monkeypatch.setenv('RATE_LIMIT_GENERAL_PER_MINUTE', '1')
    with TestClient(make_app()) as client:
        assert client.get('/hello').status_code == 200
        response = client.get('/hello', headers={'X-Request-ID': 'limit-123'})
    assert response.status_code == 429
    assert response.headers['X-Request-ID'] == 'limit-123'
    assert 1 <= int(response.headers['Retry-After']) <= 60
    body = response.json()
    assert body['code'] == 'RATE_LIMITED'
    assert body['status'] == 429
    assert body['traceId'] == 'limit-123'
    assert {'timestamp', 'status', 'code', 'message', 'details', 'traceId'} <= body.keys()


def test_disabled_limit_allows_repeated_calls(monkeypatch):
    monkeypatch.setenv('RATE_LIMIT_ENABLED', 'false')
    monkeypatch.setenv('RATE_LIMIT_GENERAL_PER_MINUTE', '1')
    with TestClient(make_app()) as client:
        assert [client.get('/hello').status_code for _ in range(5)] == [200] * 5


def test_options_preflight_is_not_limited(monkeypatch):
    monkeypatch.setenv('RATE_LIMIT_ENABLED', 'true')
    monkeypatch.setenv('RATE_LIMIT_GENERAL_PER_MINUTE', '1')
    with TestClient(make_app()) as client:
        first = client.options('/hello')
        second = client.options('/hello')
        actual = client.get('/hello')
    assert first.status_code != 429
    assert second.status_code != 429
    assert actual.status_code == 200


def test_login_has_separate_bucket(monkeypatch):
    monkeypatch.setenv('RATE_LIMIT_ENABLED', 'true')
    monkeypatch.setenv('RATE_LIMIT_GENERAL_PER_MINUTE', '1')
    monkeypatch.setenv('RATE_LIMIT_LOGIN_PER_MINUTE', '1')
    with TestClient(make_app()) as client:
        assert client.get('/hello').status_code == 200
        assert client.post('/api/v1/auth/login').status_code == 200
        assert client.post('/api/v1/auth/login').status_code == 429


def test_register_has_separate_bucket(monkeypatch):
    monkeypatch.setenv('RATE_LIMIT_ENABLED', 'true')
    monkeypatch.setenv('RATE_LIMIT_REGISTER_PER_MINUTE', '1')
    with TestClient(make_app()) as client:
        assert client.post('/api/v1/auth/register').status_code == 200
        assert client.post('/api/v1/auth/register').status_code == 429


def test_per_ip_isolation():
    assert _allow('192.0.2.1', 'general', 1, 100.0) == 0
    assert _allow('192.0.2.1', 'general', 1, 100.0) == 60
    assert _allow('192.0.2.2', 'general', 1, 100.0) == 0


def test_window_expires():
    assert _allow('192.0.2.3', 'general', 1, 100.0) == 0
    assert _allow('192.0.2.3', 'general', 1, 159.0) == 1
    assert _allow('192.0.2.3', 'general', 1, 160.0) == 0


def test_clear_rate_limits_resets_state():
    assert _allow('192.0.2.4', 'general', 1, 100.0) == 0
    assert _allow('192.0.2.4', 'general', 1, 100.0) == 60
    clear_rate_limits()
    assert _allow('192.0.2.4', 'general', 1, 100.0) == 0


def test_request_id_generated_if_missing(monkeypatch):
    monkeypatch.setenv('RATE_LIMIT_ENABLED', 'true')
    monkeypatch.setenv('RATE_LIMIT_GENERAL_PER_MINUTE', '1')
    with TestClient(make_app()) as client:
        client.get('/hello')
        response = client.get('/hello')
    assert response.status_code == 429
    assert response.headers['X-Request-ID']
    assert response.json()['traceId'] == response.headers['X-Request-ID']


def make_record(message='http_request', **extra):
    record = logging.LogRecord('app.access', logging.INFO, __file__, 1, message, (), None)
    for key, value in extra.items():
        setattr(record, key, value)
    return record


def test_json_formatter_fields():
    record = make_record(request_id='abc', method='GET', path='/hello', status=200, duration_ms=4.5)
    output = json.loads(JsonFormatter().format(record))
    assert output['level'] == 'INFO'
    assert output['logger'] == 'app.access'
    assert output['message'] == 'http_request'
    assert output['request_id'] == 'abc'
    assert output['method'] == 'GET'
    assert output['path'] == '/hello'
    assert output['status'] == 200
    assert output['duration_ms'] == 4.5
    assert 'timestamp' in output


def test_json_formatter_handles_unicode():
    output = json.loads(JsonFormatter().format(make_record('مرحبا')))
    assert output['message'] == 'مرحبا'


def test_json_formatter_hides_exception_text():
    try:
        raise RuntimeError('sensitive-exception-data')
    except RuntimeError:
        import sys
        record = make_record()
        record.exc_info = sys.exc_info()
        output = JsonFormatter().format(record)
    assert 'sensitive-exception-data' not in output
    assert json.loads(output)['exception'] == 'Unhandled exception'


def test_access_log_records_request_id_status_and_duration(caplog):
    with caplog.at_level(logging.INFO, logger='app.access'):
        with TestClient(make_app(rate=False, access=True)) as client:
            response = client.get('/hello', headers={'X-Request-ID': 'abc-123'})
    assert response.status_code == 200
    records = [r for r in caplog.records if r.name == 'app.access' and r.msg == 'http_request']
    assert records
    record = records[-1]
    assert record.request_id == 'abc-123'
    assert record.method == 'GET'
    assert record.path == '/hello'
    assert record.status == 200
    assert isinstance(record.duration_ms, (int, float))
    assert record.duration_ms >= 0


def test_access_log_does_not_log_query_or_auth_header(caplog):
    with caplog.at_level(logging.INFO, logger='app.access'):
        with TestClient(make_app(rate=False, access=True)) as client:
            client.get('/hello?token=do-not-log&password=hidden', headers={
                'Authorization': 'Bearer super-private-token',
                'X-Request-ID': 'safe-id',
            })
    records = [r for r in caplog.records if r.name == 'app.access' and r.msg == 'http_request']
    assert records
    rendered = JsonFormatter().format(records[-1])
    assert 'do-not-log' not in rendered
    assert 'super-private-token' not in rendered
    assert 'hidden' not in rendered
    assert json.loads(rendered)['path'] == '/hello'


def test_access_log_records_404(caplog):
    with caplog.at_level(logging.INFO, logger='app.access'):
        with TestClient(make_app(rate=False, access=True)) as client:
            assert client.get('/missing').status_code == 404
    records = [r for r in caplog.records if r.name == 'app.access' and r.msg == 'http_request']
    assert records[-1].status == 404


def test_invalid_log_level_rejected(monkeypatch):
    monkeypatch.setenv('LOG_LEVEL', 'VERBOSE')
    with pytest.raises(ValueError, match='LOG_LEVEL'):
        configure_json_logging()


def test_configure_json_logging_idempotent(monkeypatch):
    monkeypatch.setenv('LOG_LEVEL', 'INFO')
    root = logging.getLogger()
    old_level = root.level
    old_handlers = list(root.handlers)
    try:
        configure_json_logging()
        configure_json_logging()
        managed = [h for h in root.handlers if getattr(h, '_qaryati_json', False)]
        assert len(managed) == 1
        assert isinstance(managed[0].formatter, JsonFormatter)
    finally:
        for handler in list(root.handlers):
            if handler not in old_handlers:
                root.removeHandler(handler)
                handler.close()
        root.setLevel(old_level)
