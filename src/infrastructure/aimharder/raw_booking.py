from dataclasses import dataclass
from datetime import time

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
    limit: int
    ocupation: int

    @classmethod
    def from_dict(cls, data: dict) -> "RawBooking":
        return cls(
            id=str(data["id"]),
            class_name=data["className"],
            timeid=data["timeid"],
            limit=data.get("limit", 0),
            ocupation=data.get("ocupation", 0),
        )

    @property
    def spots_available(self) -> int:
        return self.limit - self.ocupation

    def to_gym_class(self) -> GymClass:
        return GymClass(
            id=self.id,
            name=self.class_name,
            start_time=_normalize_timeid(self.timeid),
            max_spots=self.limit,
            spots_available=self.spots_available,
        )
