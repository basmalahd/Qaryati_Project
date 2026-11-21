from pydantic import BaseModel


class GeoCandidate(BaseModel):
    latitude: float
    longitude: float
    display_name: str
    # Distance from the village's *current* coordinates (only when it has some).
    distance_km: float | None = None


class LocationSuggestions(BaseModel):
    """Suggestions only: nothing is written. Apply one with PATCH /villages/{id} (audited)."""

    village_id: int
    query: str
    current_latitude: float | None
    current_longitude: float | None
    candidates: list[GeoCandidate]
