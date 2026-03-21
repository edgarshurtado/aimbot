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
    def book_class(self, gym_class: GymClass) -> None: ...


class IGymClientFactory(ABC):
    @abstractmethod
    def create(self, email: str, password: str) -> IGymClient: ...
