import pytest
from pydantic import ValidationError

from app.core.config import AppEnv, Settings, build_settings

STRONG_SECRET = "k9Zp3QvT7xLw2NfB8mRc5YdH1sJgA6eU4oVi0XtE"
DEV_COMMITTED_SECRET = "Qaryati_Local_Dev_Secret_Key_2026_123456789"
PROD_ORIGIN = "https://app.qaryati.ps"

ENV_KEYS = ("APP_ENV", "DATABASE_URL", "JWT_SECRET_KEY", "CORS_ORIGINS")


def make(**overrides) -> Settings:
    """Build Settings from explicit values only (no .env file, init values win over env vars)."""
    values = {"database_url": "sqlite://", "jwt_secret_key": STRONG_SECRET}
    values.update(overrides)
    return Settings(_env_file=None, **values)


@pytest.fixture()
def clean_env(monkeypatch, tmp_path):
    """No config env vars and a working directory without a .env file."""
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.chdir(tmp_path)
    return monkeypatch


# --- environments -----------------------------------------------------------------------------

def test_development_config(clean_env):
    s = make(app_env="development")
    assert s.app_env is AppEnv.DEVELOPMENT
    assert s.cors_origins_list == []


def test_development_is_the_default_environment(clean_env):
    assert make().app_env is AppEnv.DEVELOPMENT


def test_test_config(clean_env):
    s = make(app_env="test", cors_origins="http://localhost:3000")
    assert s.app_env is AppEnv.TEST
    assert s.cors_origins_list == ["http://localhost:3000"]


def test_production_config_with_strong_values(clean_env):
    s = make(app_env="production", cors_origins=PROD_ORIGIN)
    assert s.app_env is AppEnv.PRODUCTION
    assert s.cors_origins_list == [PROD_ORIGIN]


def test_environment_name_is_case_insensitive(clean_env):
    assert make(app_env="  Production ", cors_origins=PROD_ORIGIN).app_env is AppEnv.PRODUCTION


def test_unknown_environment_is_rejected(clean_env):
    with pytest.raises(ValidationError):
        make(app_env="staging")


# --- CORS origins -----------------------------------------------------------------------------

def test_cors_origins_comma_separated(clean_env):
    s = make(cors_origins=" http://localhost:3000 , http://localhost:5173,, ")
    assert s.cors_origins_list == ["http://localhost:3000", "http://localhost:5173"]


def test_cors_origins_json_array(clean_env):
    s = make(cors_origins='["http://localhost:3000", "http://localhost:5173"]')
    assert s.cors_origins_list == ["http://localhost:3000", "http://localhost:5173"]


def test_cors_origins_empty_means_none(clean_env):
    assert make(cors_origins="").cors_origins_list == []


@pytest.mark.parametrize("bad", ["[not json", '{"a": 1}', "[1, 2]"])
def test_malformed_cors_origins_are_rejected_in_every_environment(clean_env, bad):
    with pytest.raises(ValidationError):
        make(app_env="development", cors_origins=bad)


def test_cors_origins_are_read_from_the_environment(clean_env):
    clean_env.setenv("DATABASE_URL", "sqlite://")
    clean_env.setenv("JWT_SECRET_KEY", STRONG_SECRET)
    clean_env.setenv("CORS_ORIGINS", "http://a.test,http://b.test")
    assert build_settings().cors_origins_list == ["http://a.test", "http://b.test"]


@pytest.mark.parametrize("app_env", ["development", "test"])
def test_wildcard_is_allowed_outside_production(clean_env, app_env):
    assert make(app_env=app_env, cors_origins="*").cors_origins_list == ["*"]


@pytest.mark.parametrize(
    "origins",
    ["*", f"{PROD_ORIGIN},*", "https://*.qaryati.ps", '["*"]'],
)
def test_wildcard_is_rejected_in_production(clean_env, origins):
    with pytest.raises(ValidationError, match="wildcard"):
        make(app_env="production", cors_origins=origins)


@pytest.mark.parametrize(
    "origin",
    ["app.qaryati.ps", "https://app.qaryati.ps/", "https://app.qaryati.ps/x", "ftp://app.qaryati.ps", "null"],
)
def test_malformed_origin_is_rejected_in_production(clean_env, origin):
    with pytest.raises(ValidationError, match="Invalid CORS origin"):
        make(app_env="production", cors_origins=origin)


def test_empty_cors_origins_are_valid_in_production(clean_env):
    assert make(app_env="production", cors_origins="").cors_origins_list == []


# --- JWT secret -------------------------------------------------------------------------------

@pytest.mark.parametrize(
    "secret",
    [
        DEV_COMMITTED_SECRET,        # the value that used to be committed in .env.example
        "t" * 64,                    # the test-suite secret: long but one repeated character
        "change_me_" * 5,
        "ChangeMe-" + "aB3$xY9!" * 4,
        "my-super-password-for-qaryati-prod-2026",  # contains the "password" marker
        "your-secret-key-goes-here-replace-me-1",
    ],
)
def test_default_weak_or_placeholder_secret_is_rejected_in_production(clean_env, secret):
    with pytest.raises(ValidationError, match="JWT_SECRET_KEY"):
        make(app_env="production", jwt_secret_key=secret)


@pytest.mark.parametrize("app_env", ["development", "test", "production"])
def test_short_secret_is_rejected_in_every_environment(clean_env, app_env):
    with pytest.raises(ValidationError, match="at least 32"):
        make(app_env=app_env, jwt_secret_key="short")


@pytest.mark.parametrize("app_env", ["development", "test"])
def test_non_production_keeps_accepting_long_secrets(clean_env, app_env):
    assert make(app_env=app_env, jwt_secret_key="t" * 64).app_env.value == app_env


# --- .env handling ----------------------------------------------------------------------------

def _write_dotenv(path, **values):
    path.write_text("".join(f"{k}={v}\n" for k, v in values.items()), encoding="utf-8")


def test_development_loads_the_env_file(clean_env, tmp_path):
    _write_dotenv(
        tmp_path / ".env",
        APP_ENV="development",
        DATABASE_URL="sqlite:///from-dotenv",
        JWT_SECRET_KEY=STRONG_SECRET,
        CORS_ORIGINS="http://from-dotenv.test",
    )
    s = build_settings()
    assert s.database_url == "sqlite:///from-dotenv"
    assert s.cors_origins_list == ["http://from-dotenv.test"]


def test_real_environment_variables_beat_the_env_file(clean_env, tmp_path):
    _write_dotenv(
        tmp_path / ".env", DATABASE_URL="sqlite:///from-dotenv", JWT_SECRET_KEY=STRONG_SECRET
    )
    clean_env.setenv("DATABASE_URL", "sqlite:///from-env")
    assert build_settings().database_url == "sqlite:///from-env"


def test_production_does_not_load_the_env_file(clean_env, tmp_path):
    _write_dotenv(
        tmp_path / ".env",
        DATABASE_URL="sqlite:///from-dotenv",
        JWT_SECRET_KEY=STRONG_SECRET,
        CORS_ORIGINS=PROD_ORIGIN,
    )
    clean_env.setenv("APP_ENV", "production")
    # Everything required lives only in .env, so a production load must fail instead of using it.
    with pytest.raises(ValidationError) as exc:
        build_settings()
    missing = {err["loc"][0] for err in exc.value.errors()}
    assert {"database_url", "jwt_secret_key"} <= missing


def test_production_ignores_env_file_values_but_uses_real_variables(clean_env, tmp_path):
    _write_dotenv(
        tmp_path / ".env",
        DATABASE_URL="sqlite:///from-dotenv",
        JWT_SECRET_KEY=DEV_COMMITTED_SECRET,
        CORS_ORIGINS="https://from-dotenv.test",
    )
    clean_env.setenv("APP_ENV", "production")
    clean_env.setenv("DATABASE_URL", "sqlite:///from-env")
    clean_env.setenv("JWT_SECRET_KEY", STRONG_SECRET)
    s = build_settings()
    assert s.database_url == "sqlite:///from-env"
    assert s.jwt_secret_key == STRONG_SECRET
    assert s.cors_origins_list == []  # not taken from .env


def test_production_declared_only_in_env_file_is_refused(clean_env, tmp_path):
    _write_dotenv(
        tmp_path / ".env",
        APP_ENV="production",
        DATABASE_URL="sqlite:///from-dotenv",
        JWT_SECRET_KEY=STRONG_SECRET,
        CORS_ORIGINS=PROD_ORIGIN,
    )
    with pytest.raises(RuntimeError, match=r"\.env"):
        build_settings()
