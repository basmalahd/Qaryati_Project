from types import SimpleNamespace

import pytest

from app.core import security
from app.core.errors import ConflictError, NotFoundError, UnauthorizedError
from app.models.user import Role, User
from app.schemas.auth import RegisterRequest
from app.services.auth_service import AuthService
from tests.unit.fakes import make_db


class FakeUsers:
    def __init__(self):
        self.users = {}

    def add(self, user):
        user.id = len(self.users) + 1
        self.users[user.id] = user
        return user

    def get_by_email(self, email):
        return next((u for u in self.users.values() if u.email == email), None)

    def get_by_id(self, user_id):
        return self.users.get(user_id)


def make_service():
    calls: list[str] = []
    service = AuthService(make_db(calls))
    service.users = FakeUsers()
    return service, calls


def seed(service, email="ali@example.com", password="Password123", active=True, role="viewer"):
    user = User(email=email, full_name="Ali", hashed_password=security.hash_password(password),
                role=role, is_active=active)
    return service.users.add(user)


def test_register_lowercases_email_hashes_password_and_creates_a_viewer():
    service, calls = make_service()
    user = service.register(RegisterRequest(email="Ali@Example.com", password="Password123", full_name=" Ali "))

    assert user.email == "ali@example.com" and user.full_name == "Ali"
    assert user.role == Role.VIEWER.value
    assert user.hashed_password != "Password123"
    assert security.verify_password("Password123", user.hashed_password)
    assert calls == ["commit"]


def test_register_rejects_a_duplicate_email_without_committing():
    service, calls = make_service()
    seed(service)
    with pytest.raises(ConflictError):
        service.register(RegisterRequest(email="ALI@example.com", password="Password123", full_name="Ali"))
    assert calls == []


@pytest.mark.parametrize("email, password, active", [
    ("nobody@example.com", "Password123", True),  # unknown email
    ("ali@example.com", "WrongPassword1", True),  # wrong password
    ("ali@example.com", "Password123", False),    # deactivated account
])
def test_login_failures_share_one_message(email, password, active):
    service, _ = make_service()
    seed(service, active=active)
    with pytest.raises(UnauthorizedError) as error:
        service.authenticate(email, password)
    assert error.value.message == "Invalid email or password"  # no user enumeration


def test_login_issues_working_tokens():
    service, _ = make_service()
    user = seed(service)
    tokens = service.login("ALI@example.com", "Password123")
    assert security.decode_token(tokens.access_token, security.ACCESS)["sub"] == str(user.id)
    assert security.decode_token(tokens.refresh_token, security.REFRESH)["sub"] == str(user.id)


def test_refresh_rejects_deactivated_users_and_wrong_token_types():
    service, _ = make_service()
    user = seed(service)
    tokens = service.login("ali@example.com", "Password123")
    assert service.refresh(tokens.refresh_token).token_type == "bearer"

    with pytest.raises(UnauthorizedError):
        service.refresh(tokens.access_token)  # an access token is not a refresh token
    user.is_active = False
    with pytest.raises(UnauthorizedError):
        service.refresh(tokens.refresh_token)


def test_change_role_of_unknown_user_is_not_found():
    service, calls = make_service()
    with pytest.raises(NotFoundError):
        service.change_role(99, Role.EDITOR)
    user = seed(service)
    assert service.change_role(user.id, Role.EDITOR).role == "editor"
    assert calls == ["commit"]
