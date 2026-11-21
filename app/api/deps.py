from functools import lru_cache

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core import security
from app.core.config import settings
from app.core.errors import ForbiddenError, UnauthorizedError
from app.db.session import get_db
from app.integrations.geocoding import GeocodingProvider, build_geocoder
from app.models.user import Role, User
from app.repositories.user_repository import UserRepository

# auto_error=False so *we* produce the unified error format instead of FastAPI's default.
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if creds is None:
        raise UnauthorizedError("Missing bearer token")
    payload = security.decode_token(creds.credentials, security.ACCESS)
    user = UserRepository(db).get_by_id(int(payload["sub"]))
    if not user or not user.is_active:
        raise UnauthorizedError("User no longer exists or is inactive")
    return user


def require_roles(*roles: Role):
    allowed = {r.value for r in roles}

    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise ForbiddenError("You do not have permission to perform this action")
        return user

    return checker


@lru_cache
def get_geocoder() -> GeocodingProvider:
    """One shared instance per process so the cache and the rate-limit throttle are shared."""
    return build_geocoder(settings)
