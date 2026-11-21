from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.schemas.source import SourceBrief

NameType = Literal["alternative_spelling", "transliteration", "former", "historical"]
Name150 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)]
Language = Annotated[str, Field(pattern=r"^[a-z]{2}$", description="ISO 639-1 code, e.g. ar, en")]


class VillageNameCreate(BaseModel):
    name: Name150
    language: Language = "ar"
    name_type: NameType
    period_note: str | None = Field(default=None, max_length=200)
    source_id: int | None = Field(default=None, ge=1)


class VillageNameUpdate(BaseModel):
    name: Name150 | None = None
    language: Language | None = None
    name_type: NameType | None = None
    period_note: str | None = Field(default=None, max_length=200)
    source_id: int | None = Field(default=None, ge=1)

    @field_validator("name", "language", "name_type")
    @classmethod
    def required_fields_cannot_be_null(cls, v):
        if v is None:
            raise ValueError("cannot be null")
        return v


class VillageNameItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    village_id: int
    name: str
    language: str
    name_type: str
    period_note: str | None
    source: SourceBrief | None
    created_at: datetime
