from dataclasses import dataclass
from datetime import date, datetime, time

from domain.models import GymClass


def _normalize_timeid(timeid: str) -> time:
    """Convert '1100_60' → time(11, 0), '0830_60' → time(8, 30)."""
    raw = timeid.split("_")[0].zfill(4)
    return time(int(raw[:2]), int(raw[2:]))


@dataclass
class RawBooking:
    id: str
    class_name: str
    timeid: str

    @classmethod
    def from_dict(cls, data: dict) -> "RawBooking":
        return cls(
            id=str(data["id"]),
            class_name=data["className"],
            timeid=data["timeid"],
        )

    def to_gym_class(self, day: date) -> GymClass:
        return GymClass(
            name=self.class_name,
            class_start=datetime.combine(day, _normalize_timeid(self.timeid)),
        )
