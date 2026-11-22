from app.core.errors import UnprocessableError
from app.models.content import EconomicItem, Facility, HeritageItem, HistoricalEvent, Landmark
from app.services.village_child_service import VillageChildService


class EventService(VillageChildService):
    model = HistoricalEvent
    entity_type = "historical_event"
    label = "Historical event"

    def ordering(self) -> list:  # timeline order; undated ("period only") entries last
        return [HistoricalEvent.year.asc().nulls_last(), HistoricalEvent.id]

    def validate_state(self, state: dict) -> None:
        if state.get("year") is None and not state.get("date_note"):
            raise UnprocessableError(
                "Provide a year or a date_note", [{"field": "year", "message": "year or date_note required"}]
            )

    def list(self, village_id: int, from_year: int | None, to_year: int | None):
        if from_year is not None and to_year is not None and from_year > to_year:
            raise UnprocessableError(
                "from_year must not be after to_year", [{"field": "from_year", "message": "must be <= to_year"}]
            )
        extra = []
        if from_year is not None:
            extra.append(HistoricalEvent.year >= from_year)
        if to_year is not None:
            extra.append(HistoricalEvent.year <= to_year)
        return self._list(village_id, extra=extra)


class LandmarkService(VillageChildService):
    model = Landmark
    entity_type = "landmark"
    label = "Landmark"
    unique_keys = ("name_ar",)

    def ordering(self) -> list:
        return [Landmark.name_ar, Landmark.id]

    def validate_state(self, state: dict) -> None:
        if (state.get("latitude") is None) != (state.get("longitude") is None):
            raise UnprocessableError(
                "latitude and longitude must be provided together",
                [{"field": "latitude", "message": "must be set together with longitude"}],
            )

    def list(self, village_id: int, category: str | None):
        return self._list(village_id, {"category": category})


class HeritageService(VillageChildService):
    model = HeritageItem
    entity_type = "heritage_item"
    label = "Heritage item"
    unique_keys = ("name", "category")

    def ordering(self) -> list:
        return [HeritageItem.name, HeritageItem.id]

    def list(self, village_id: int, category: str | None):
        return self._list(village_id, {"category": category})


class EconomyService(VillageChildService):
    model = EconomicItem
    entity_type = "economic_item"
    label = "Economic item"
    unique_keys = ("name", "category")

    def ordering(self) -> list:
        return [EconomicItem.name, EconomicItem.id]

    def list(self, village_id: int, category: str | None):
        return self._list(village_id, {"category": category})


class FacilityService(VillageChildService):
    model = Facility
    entity_type = "facility"
    label = "Facility"
    unique_keys = ("name", "facility_type")

    def ordering(self) -> list:
        return [Facility.name, Facility.id]

    def list(self, village_id: int, facility_type: str | None):
        return self._list(village_id, {"facility_type": facility_type})
