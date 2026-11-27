from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.source import SourceBrief

VerificationStatus = Literal["pending", "verified", "disputed"]
Population = Annotated[int, Field(ge=0, le=100_000_000)]
Year = Annotated[int, Field(ge=1800, le=2100)]


def _not_in_future(v: int | None) -> int | None:
    if v is not None and v > date.today().year:
        raise ValueError("reference_year cannot be in the future")
    return v


class PopulationCreate(BaseModel):
    population: Population
    reference_year: Year
    source_id: int = Field(ge=1)  # provenance is mandatory
    notes: str | None = Field(default=None, max_length=2000)

    _year_check = field_validator("reference_year")(_not_in_future)


class PopulationUpdate(BaseModel):
    population: Population | None = None
    reference_year: Year | None = None
    source_id: int | None = Field(default=None, ge=1)
    notes: str | None = Field(default=None, max_length=2000)

    _year_check = field_validator("reference_year")(_not_in_future)

    @field_validator("population", "reference_year", "source_id")
    @classmethod
    def required_fields_cannot_be_null(cls, v):
        if v is None:
            raise ValueError("cannot be null")
        return v


class PopulationStatusUpdate(BaseModel):
    status: VerificationStatus


class PopulationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    village_id: int
    population: int
    reference_year: int
    verification_status: str
    notes: str | None
    source: SourceBrief
    # True when another source reports a different value for the same year.
    has_conflict: bool = False
    created_at: datetime
    updated_at: datetime


class LatestVillagePopulation(BaseModel):
    village_id: int
    name_ar: str
    name_en: str | None
    governorate_id: int
    population: int
    reference_year: int
    verification_status: VerificationStatus
    source_id: int
