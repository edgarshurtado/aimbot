from abc import ABC, abstractmethod
from datetime import datetime


class IJobScheduler(ABC):
    @abstractmethod
    def start(self) -> None: ...

    @abstractmethod
    def schedule_job(self, run_at: datetime, user_id: int, booking_date: datetime, class_name: str) -> str: ...

    @abstractmethod
    def remove_job(self, job_id: str) -> None: ...
