from sqlalchemy.orm import Session

from app.core.errors import (
    BadGatewayError, NotFoundError, ServiceUnavailableError, UnprocessableError,
)
from app.core.geo import haversine_km
from app.integrations.geocoding import (
    GeocodingBadResponseError, GeocodingProvider, GeocodingUnavailableError, GeoLocation,
)
from app.repositories.village_repository import VillageRepository
from app.schemas.geocoding import GeoCandidate, LocationSuggestions

COUNTRY_CODE = "ps"


class LocationService:
    """Uses the geocoding port to *suggest* coordinates. It never overwrites village data:
    a human applies a suggestion through the normal (audited) update endpoint."""

    def __init__(self, db: Session, geocoder: GeocodingProvider):
        self.villages = VillageRepository(db)
        self.geocoder = geocoder

    def search(self, q: str, limit: int) -> list[GeoCandidate]:
        query = " ".join(q.split())
        if len(query) < 2:
            raise UnprocessableError("Query is too short", [{"field": "q", "message": "min 2 characters"}])
        return [self._candidate(g) for g in self._search(query, limit)]

    def suggest_for_village(self, village_id: int) -> LocationSuggestions:
        village = self.villages.get_detail(village_id)
        if not village:
            raise NotFoundError("Village not found")

        gov = village.governorate
        query = ", ".join([village.name_en or village.name_ar, gov.name_en or gov.name_ar])
        has_coordinates = village.latitude is not None and village.longitude is not None
        candidates = [
            self._candidate(g, village.latitude, village.longitude if has_coordinates else None)
            for g in self._search(query, 5)
        ]
        return LocationSuggestions(
            village_id=village.id,
            query=query,
            current_latitude=village.latitude,
            current_longitude=village.longitude,
            candidates=candidates,
        )

    # ---- helpers -----------------------------------------------------
    def _search(self, query: str, limit: int) -> list[GeoLocation]:
        """The one place where external failures become our own API errors."""
        try:
            return self.geocoder.search(query, limit=limit, country_code=COUNTRY_CODE)
        except GeocodingUnavailableError:
            raise ServiceUnavailableError(
                "Geocoding service is temporarily unavailable, please try again later",
                code="GEOCODING_UNAVAILABLE",
            )
        except GeocodingBadResponseError:
            raise BadGatewayError(
                "Geocoding provider returned an unusable response", code="GEOCODING_BAD_RESPONSE"
            )

    @staticmethod
    def _candidate(g: GeoLocation, cur_lat: float | None = None, cur_lon: float | None = None):
        distance = None
        if cur_lat is not None and cur_lon is not None:
            distance = round(haversine_km(cur_lat, cur_lon, g.latitude, g.longitude), 2)
        return GeoCandidate(
            latitude=g.latitude, longitude=g.longitude, display_name=g.display_name,
            distance_km=distance,
        )
