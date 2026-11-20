import uuid
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from app.core.config import settings
from app.core.errors import UnauthorizedError

_hasher = PasswordHasher()
# Verified against when the email does not exist, so login timing doesn't reveal which emails exist.
DUMMY_HASH = _hasher.hash("not-a-real-password")

ACCESS = "access"
REFRESH = "refresh"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return _hasher.verify(hashed, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def create_token(subject: str, token_type: str, expires_delta: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "type": token_type,
        "jti": uuid.uuid4().hex,
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(subject: str) -> str:
    return create_token(subject, ACCESS, timedelta(minutes=settings.access_token_minutes))


def create_refresh_token(subject: str) -> str:
    return create_token(subject, REFRESH, timedelta(days=settings.refresh_token_days))


def decode_token(token: str, expected_type: str) -> dict:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError:
        raise UnauthorizedError("Token has expired")
    except jwt.PyJWTError:
        raise UnauthorizedError("Invalid token")
    if payload.get("type") != expected_type:
        raise UnauthorizedError("Wrong token type")
    return payload
