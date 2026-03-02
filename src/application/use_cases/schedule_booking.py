from datetime import datetime

from domain.models import BookingGoal
from domain.ports.booking_repository import IBookingRepository
from domain.ports.gym_client import IGymPlatformConfig
from domain.ports.scheduler import IJobScheduler
from domain.ports.user_repository import IUserRepository


class ScheduleBookingUseCase:
    def __init__(
        self,
        user_repo: IUserRepository,
        booking_repo: IBookingRepository,
        scheduler: IJobScheduler,
        platform_config: IGymPlatformConfig,
    ) -> None:
        self._user_repo = user_repo
        self._booking_repo = booking_repo
        self._scheduler = scheduler
        self._platform_config = platform_config

    def execute(self, user_id: int, booking_date: datetime, class_name: str) -> None:
        user = self._user_repo.get_user(user_id)
        if user is None:
            raise ValueError(f"User {user_id} not found")

        trigger = self._platform_config.booking_trigger_time(booking_date)
        job_id = self._scheduler.schedule_job(
            run_at=trigger,
            user_id=user_id,
            booking_date=booking_date,
            class_name=class_name,
        )
        self._booking_repo.add_booking_goal(
            user_id,
            BookingGoal(booking_date=booking_date, name=class_name, job_id=job_id),
        )
