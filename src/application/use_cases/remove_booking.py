from domain.models import BookingGoal
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

    def execute(self, user_id: int, booking_goal: BookingGoal) -> None:
        try:
            self._scheduler.remove_job(user_id, booking_goal)
        except Exception:
            pass
        self._booking_repo.remove_booking_goal(user_id, booking_goal)
