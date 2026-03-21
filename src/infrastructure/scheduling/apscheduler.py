from datetime import datetime
from typing import Callable

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger

from domain.models import BookingGoal
from domain.ports.scheduler import IJobScheduler


class APSchedulerAdapter(IJobScheduler):
    def __init__(self, on_job_execute: Callable[[int, datetime, str], None]) -> None:
        self._handler = on_job_execute
        self._scheduler = BackgroundScheduler()

    def start(self) -> None:
        self._scheduler.start()

    def schedule_job(self, run_at: datetime, goal: BookingGoal) -> None:
        self._scheduler.add_job(
            self._handler,
            trigger=DateTrigger(run_date=run_at),
            args=[goal.user_id, goal.booking_date, goal.name],
            id=self._job_id(goal),
            misfire_grace_time=None,  # always fire even if missed
        )

    def remove_job(self, goal: BookingGoal) -> None:
        self._scheduler.remove_job(self._job_id(goal))

    @staticmethod
    def _job_id(goal: BookingGoal) -> str:
        return f"{goal.user_id}_{goal.booking_date.isoformat()}_{goal.name}"
