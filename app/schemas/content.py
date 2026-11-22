from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import (
    BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator,
)

from app.schemas.source import SourceBrief

LandmarkCategory = Literal[
    "heritage_site", "archaeological_site", "traditional_building", "spring",
    "religious_site", "viewpoint", "other",
]
HeritageCategory = Literal["craft", "food", "agricultural_practice", "custom", "other"]
EconomicCategory = Literal["crop", "agricultural_product", "livestock", "craft", "industry", "trade", "other"]
FacilityType = Literal["school", "clinic", "library", "community_center", "park", "sports_facility", "other"]

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Name150 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)]
DateNote = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Description = Annotated[str, Field(max_length=5000)]
EventYear = Annotated[int, Field(ge=-3000, le=2100)]
Latitude = Annotated[float, Field(ge=-90, le=90)]
Longitude = Annotated[float, Field(ge=-180, le=180)]
SourceId = Annotated[int, Field(ge=1)]


def _not_in_future(v):
    if v is not None and v > date.today().year:
        raise ValueError("year cannot be in the future")
    return v


def _not_null(v):
    if v is None:
        raise ValueError("cannot be null")
    return v


class _Read(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    village_id: int
    source: SourceBrief | None
    created_at: datetime


# ---------------- history / timeline ----------------
class EventCreate(BaseModel):
    title: Title
    description: Description | None = None
    year: EventYear | None = None
    date_note: DateNote | None = None
    source_id: SourceId | None = None

    _future = field_validator("year")(_not_in_future)

    @model_validator(mode="after")
    def needs_a_time(self):
        if self.year is None and self.date_note is None:
            raise ValueError("provide a year or a date_note")
        return self


class EventUpdate(BaseModel):
    title: Title | None = None
    description: Description | None = None
    year: EventYear | None = None
    date_note: DateNote | None = None
    source_id: SourceId | None = None

    _future = field_validator("year")(_not_in_future)
    _title_required = field_validator("title")(_not_null)


class EventRead(_Read):
    title: str
    description: str | None
    year: int | None
    date_note: str | None


# ---------------- landmarks ----------------
class LandmarkCreate(BaseModel):
    name_ar: Name150
    name_en: Name150 | None = None
    category: LandmarkCategory
    description: Description | None = None
    latitude: Latitude | None = None
    longitude: Longitude | None = None
    source_id: SourceId | None = None

    @model_validator(mode="after")
    def coordinates_come_in_pairs(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be provided together")
        return self


class LandmarkUpdate(BaseModel):
    name_ar: Name150 | None = None
    name_en: Name150 | None = None
    category: LandmarkCategory | None = None
    description: Description | None = None
    latitude: Latitude | None = None
    longitude: Longitude | None = None
    source_id: SourceId | None = None

    _required = field_validator("name_ar", "category")(_not_null)


class LandmarkRead(_Read):
    name_ar: str
    name_en: str | None
    category: str
    description: str | None
    latitude: float | None
    longitude: float | None


# ---------------- heritage ----------------
class HeritageCreate(BaseModel):
    name: Title
    category: HeritageCategory
    description: Description | None = None
    source_id: SourceId | None = None


class HeritageUpdate(BaseModel):
    name: Title | None = None
    category: HeritageCategory | None = None
    description: Description | None = None
    source_id: SourceId | None = None

    _required = field_validator("name", "category")(_not_null)


class HeritageRead(_Read):
    name: str
    category: str
    description: str | None


# ---------------- economy ----------------
class EconomicCreate(BaseModel):
    name: Title
    category: EconomicCategory
    description: Description | None = None
    source_id: SourceId | None = None


class EconomicUpdate(BaseModel):
    name: Title | None = None
    category: EconomicCategory | None = None
    description: Description | None = None
    source_id: SourceId | None = None

    _required = field_validator("name", "category")(_not_null)


class EconomicRead(_Read):
    name: str
    category: str
    description: str | None


# ---------------- facilities ----------------
class FacilityCreate(BaseModel):
    name: Title
    facility_type: FacilityType
    description: Description | None = None
    source_id: SourceId | None = None


class FacilityUpdate(BaseModel):
    name: Title | None = None
    facility_type: FacilityType | None = None
    description: Description | None = None
    source_id: SourceId | None = None

    _required = field_validator("name", "facility_type")(_not_null)


class FacilityRead(_Read):
    name: str
    facility_type: str
    description: str | None
