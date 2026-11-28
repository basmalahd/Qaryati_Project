from datetime import timedelta

from sqlalchemy.orm import Session

from app.core import security
from app.core.config import settings
from app.core.errors import ConflictError, NotFoundError, UnauthorizedError
from app.models.user import Role, User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import RegisterRequest, TokenResponse
from app.services.audit_service import AuditService


class AuthService:
    """Business rules for accounts. Knows nothing about HTTP."""

    def __init__(self, db: Session):
        self.db = db
        self.users = UserRepository(db)
        self.audit = AuditService(db)

    def register(self, data: RegisterRequest) -> User:
        email = data.email.lower()
        if self.users.get_by_email(email):
            raise ConflictError("A user with this email already exists")
        # Public registration always creates the least-privileged role.
        user = User(
            email=email,
            full_name=data.full_name.strip(),
            hashed_password=security.hash_password(data.password),
            role=Role.VIEWER.value,
        )
        self.users.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def authenticate(self, email: str, password: str) -> User:
        user = self.users.get_by_email(email.lower())
        # Always run one verification so timing doesn't leak whether the email exists.
        hashed = user.hashed_password if user else security.DUMMY_HASH
        valid = security.verify_password(password, hashed)
        if not user or not valid or not user.is_active:
            raise UnauthorizedError("Invalid email or password")
        return user

    def issue_tokens(self, user: User) -> TokenResponse:
        return TokenResponse(
            access_token=security.create_access_token(str(user.id)),
            refresh_token=security.create_refresh_token(str(user.id)),
            expires_in=int(timedelta(minutes=settings.access_token_minutes).total_seconds()),
        )

    def login(self, email: str, password: str) -> TokenResponse:
        return self.issue_tokens(self.authenticate(email, password))

    def refresh(self, refresh_token: str) -> TokenResponse:
        payload = security.decode_token(refresh_token, security.REFRESH)
        user = self.users.get_by_id(int(payload["sub"]))
        if not user or not user.is_active:
            raise UnauthorizedError("User no longer exists or is inactive")
        return self.issue_tokens(user)

    def change_role(self, user_id: int, role: Role, actor: User) -> User:
        user = self.users.get_by_id(user_id)
        if not user:
            raise NotFoundError("User not found")
        before = {"role": user.role}
        user.role = role.value
        self.audit.record(
            actor, "update", "user", user.id,
            {"before": before, "after": {"role": user.role}},
        )
        self.db.commit()
        self.db.refresh(user)
        return user