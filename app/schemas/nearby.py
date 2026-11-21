from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.schemas.source import SourceBrief

RelationType = Literal["borders", "nearby", "nearest_city"]
Direction = Literal["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
PlaceName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)]


class NearbyCreate(BaseModel):
    related_village_id: int | None = Field(default=None, ge=1)
    place_name: PlaceName | None = None
    relation_type: RelationType
    distance_km: float | None = Field(default=None, ge=0, le=1000)
    direction: Direction | None = None
    source_id: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def exactly_one_target(self):
        if (self.related_village_id is None) == (self.place_name is None):
            raise ValueError("provide exactly one of related_village_id or place_name")
        return self


class VillageBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    name_ar: str
    name_en: str | None


class NearbyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    village_id: int
    related_village: VillageBrief | None
    place_name: str | None
    relation_type: str
    distance_km: float | None
    direction: str | None
    source: SourceBrief | None
    created_at: datetime
