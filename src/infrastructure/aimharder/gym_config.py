from abc import abstractmethod
from datetime import datetime, timedelta

from domain.ports.gym_config import IGymConfig


class IAimHarderGym(IGymConfig):
    @property
    @abstractmethod
    def box_id(self) -> int: ...

    @property
    @abstractmethod
    def box_name(self) -> str: ...

    @property
    @abstractmethod
    def days_in_advance(self) -> int: ...

    def booking_trigger_time(self, class_start: datetime) -> datetime:
        return class_start - timedelta(days=self.days_in_advance)
