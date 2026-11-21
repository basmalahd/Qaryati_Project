from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

SourceType = Literal["book", "census", "official", "website", "article", "oral_history", "other"]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
Url = Annotated[str, Field(max_length=500, pattern=r"^https?://\S+$")]


class SourceCreate(BaseModel):
    title: Title
    source_type: SourceType = "other"
    author: str | None = Field(default=None, max_length=200)
    url: Url | None = None
    publication_year: int | None = Field(default=None, ge=1000, le=2100)
    notes: str | None = Field(default=None, max_length=5000)


class SourceUpdate(BaseModel):
    title: Title | None = None
    source_type: SourceType | None = None
    author: str | None = Field(default=None, max_length=200)
    url: Url | None = None
    publication_year: int | None = Field(default=None, ge=1000, le=2100)
    notes: str | None = Field(default=None, max_length=5000)

    @field_validator("title", "source_type")
    @classmethod
    def required_fields_cannot_be_null(cls, v):
        if v is None:
            raise ValueError("cannot be null")
        return v


class SourceBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    source_type: str
    publication_year: int | None


class SourceRead(SourceBrief):
    author: str | None
    url: str | None
    notes: str | None
    created_at: datetime
