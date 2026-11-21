from datetime import datetime
from typing import Annotated

from pydantic import (
    BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator,
)

from app.schemas.governorate import GovernorateRead

Name150 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)]
Slug = Annotated[str, Field(min_length=1, max_length=150, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")]
Latitude = Annotated[float, Field(ge=-90, le=90)]
Longitude = Annotated[float, Field(ge=-180, le=180)]
Elevation = Annotated[float, Field(ge=-500, le=3000)]  # metres (Dead Sea is about -430)
Area = Annotated[float, Field(gt=0, le=100000)]  # square kilometres


class VillageCreate(BaseModel):
    slug: Slug
    name_ar: Name150
    name_en: Name150 | None = None
    name_origin: str | None = Field(default=None, max_length=5000)
    historical_overview: str | None = Field(default=None, max_length=20000)
    latitude: Latitude | None = None
    longitude: Longitude | None = None
    elevation_m: Elevation | None = None
    area_km2: Area | None = None
    governorate_id: int = Field(ge=1)

    @model_validator(mode="after")
    def coordinates_come_in_pairs(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be provided together")
        return self


class VillageUpdate(BaseModel):
    """Partial update: only fields present in the request are changed."""

    slug: Slug | None = None
    name_ar: Name150 | None = None
    name_en: Name150 | None = None
    name_origin: str | None = Field(default=None, max_length=5000)
    historical_overview: str | None = Field(default=None, max_length=20000)
    latitude: Latitude | None = None
    longitude: Longitude | None = None
    elevation_m: Elevation | None = None
    area_km2: Area | None = None
    governorate_id: int | None = Field(default=None, ge=1)

    @field_validator("slug", "name_ar", "governorate_id")
    @classmethod
    def required_fields_cannot_be_null(cls, v):
        if v is None:
            raise ValueError("cannot be null")
        return v


class VillageNameRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    language: str
    name_type: str
    period_note: str | None


class VillageSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    name_ar: str
    name_en: str | None
    governorate: GovernorateRead


class VillageDetail(VillageSummary):
    name_origin: str | None
    historical_overview: str | None
    latitude: float | None
    longitude: float | None
    elevation_m: float | None
    area_km2: float | None
    names: list[VillageNameRead]
    created_at: datetime
    updated_at: datetime
