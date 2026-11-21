from sqlalchemy.orm import Session

from app.core.errors import ConflictError
from app.models.governorate import Governorate
from app.models.user import User
from app.repositories.governorate_repository import GovernorateRepository
from app.schemas.governorate import GovernorateCreate
from app.services.audit_service import AuditService


class GovernorateService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = GovernorateRepository(db)
        self.audit = AuditService(db)

    def list_all(self) -> list[Governorate]:
        return self.repo.list_all()

    def create(self, data: GovernorateCreate, actor: User) -> Governorate:
        if self.repo.get_by_name_ar(data.name_ar):
            raise ConflictError("A governorate with this name already exists")
        gov = self.repo.add(Governorate(name_ar=data.name_ar, name_en=data.name_en))
        self.audit.record(
            actor, "create", "governorate", gov.id,
            {"after": {"name_ar": gov.name_ar, "name_en": gov.name_en}},
        )
        self.db.commit()
        self.db.refresh(gov)
        return gov
