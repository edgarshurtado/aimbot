from abc import ABC, abstractmethod
from datetime import datetime
from domain.models import GymClass


class IGymPlatformConfig(ABC):
    @abstractmethod
    def booking_trigger_time(self, class_date: datetime) -> datetime: ...


class IGymClient(ABC):
    @abstractmethod
    def get_classes(self, target_day: datetime) -> list[GymClass]: ...

    @abstractmethod
    def book_class(self, target_day: datetime, class_id: str) -> None: ...


class IGymClientFactory(ABC):
    @abstractmethod
    def create(self, email: str, password: str) -> IGymClient: ...
