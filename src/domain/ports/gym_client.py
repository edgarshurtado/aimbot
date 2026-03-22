from abc import ABC, abstractmethod
from datetime import datetime
from domain.models import GymClass, User


class IGymClient(ABC):
    @abstractmethod
    def get_classes(self, target_day: datetime) -> list[GymClass]: ...

    @abstractmethod
    def book_class(self, gym_class: GymClass) -> None: ...


class IGymClientFactory(ABC):
    @abstractmethod
    def create(self, user: User) -> IGymClient: ...
