from abc import ABC, abstractmethod
from datetime import datetime

from domain.models import BookingGoal


class IJobScheduler(ABC):
    @abstractmethod
    def start(self) -> None: ...

    @abstractmethod
    def schedule_job(self, run_at: datetime, goal: BookingGoal) -> None: ...

    @abstractmethod
    def remove_job(self, goal: BookingGoal) -> None: ...
