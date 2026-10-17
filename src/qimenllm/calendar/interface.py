"""Time conventions are explicit; no calendar algorithm is guessed or bundled."""
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class TimeContext:
    datetime_original: str
    timezone: str | None
    location: str | None
    calendar_type: str | None
    day_boundary_convention: str | None
    solar_time_convention: str | None


class CalendarEngine(Protocol):
    def normalize(self, context: TimeContext, method_id: str) -> dict: ...


class UnimplementedCalendar:
    def normalize(self, context: TimeContext, method_id: str) -> dict:
        raise NotImplementedError('Calendar conventions and source algorithms have not been provided')
