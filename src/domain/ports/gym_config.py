from abc import ABC, abstractmethod
from datetime import datetime


class IGymConfig(ABC):
    @abstractmethod
    def booking_trigger_time(self, class_start: datetime) -> datetime: ...
