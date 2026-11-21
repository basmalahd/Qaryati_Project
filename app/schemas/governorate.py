from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

Name100 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class GovernorateCreate(BaseModel):
    name_ar: Name100
    name_en: Name100 | None = None


class GovernorateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name_ar: str
    name_en: str | None


class GovernorateVillageCount(BaseModel):
    governorate_id: int
    name_ar: str
    name_en: str | None
    village_count: int
