from datetime import datetime
from typing import Callable

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger

from domain.models import BookingGoal
from domain.ports.scheduler import IJobScheduler


class APSchedulerAdapter(IJobScheduler):
    def __init__(self, on_job_execute: Callable[[int, BookingGoal], None]) -> None:
        self._handler = on_job_execute
        self._scheduler = BackgroundScheduler()

    def start(self) -> None:
        self._scheduler.start()

    def schedule_job(
        self,
        run_at: datetime,
        user_id: int,
        booking_goal: BookingGoal,
    ) -> None:
        self._scheduler.add_job(
            self._handler,
            trigger=DateTrigger(run_date=run_at),
            args=[user_id, booking_goal],
            id=self._job_id(user_id, booking_goal),
            misfire_grace_time=None,  # always fire even if missed
            # A repeated goal is a no-op, matching the repository's dedup. Without
            # this the scheduler raises ConflictingIdError and, going first, turns
            # a harmless repeat into a reported failure.
            replace_existing=True,
        )

    def remove_job(self, user_id: int, booking_goal: BookingGoal) -> None:
        self._scheduler.remove_job(self._job_id(user_id, booking_goal))

    @staticmethod
    def _job_id(user_id: int, booking_goal: BookingGoal) -> str:
        return f"{user_id}_{booking_goal.class_start.isoformat()}_{booking_goal.class_name}"
