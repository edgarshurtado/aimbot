from datetime import datetime

from domain.models import BookingGoal
from domain.ports.booking_repository import IBookingRepository
from domain.ports.gym_config import IGymConfig
from domain.ports.scheduler import IJobScheduler
from domain.ports.user_repository import IUserRepository


class ScheduleBookingUseCase:
    def __init__(
        self,
        user_repo: IUserRepository,
        booking_repo: IBookingRepository,
        scheduler: IJobScheduler,
        gym_config: IGymConfig,
    ) -> None:
        self._user_repo = user_repo
        self._booking_repo = booking_repo
        self._scheduler = scheduler
        self._gym_config = gym_config

    def execute(self, user_id: int, class_start: datetime, class_name: str) -> None:
        user = self._user_repo.get_user(user_id)
        if user is None:
            raise ValueError(f"User {user_id} not found")

        booking_goal = BookingGoal(class_start=class_start, class_name=class_name)
        trigger = self._gym_config.booking_trigger_time(class_start)
        self._scheduler.schedule_job(
            run_at=trigger,
            user_id=user_id,
            booking_goal=booking_goal,
        )
        self._booking_repo.add_booking_goal(user_id, booking_goal)
