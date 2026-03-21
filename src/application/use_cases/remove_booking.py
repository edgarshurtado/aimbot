from datetime import datetime

from domain.ports.booking_repository import IBookingRepository
from domain.ports.scheduler import IJobScheduler


class RemoveBookingUseCase:
    def __init__(
        self,
        booking_repo: IBookingRepository,
        scheduler: IJobScheduler,
    ) -> None:
        self._booking_repo = booking_repo
        self._scheduler = scheduler

    def execute(self, user_id: int, booking_date: datetime, class_name: str) -> None:
        self._scheduler.remove_job(user_id, booking_date, class_name)
        self._booking_repo.remove_booking_goal(user_id, booking_date, class_name)
