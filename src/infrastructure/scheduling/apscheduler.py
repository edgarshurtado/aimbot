from datetime import datetime
from typing import Callable

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger

from domain.ports.scheduler import IJobScheduler


class APSchedulerAdapter(IJobScheduler):
    def __init__(self, on_job_execute: Callable[[int, datetime, str], None]) -> None:
        self._handler = on_job_execute
        self._scheduler = BackgroundScheduler()

    def start(self) -> None:
        self._scheduler.start()

    def schedule_job(
        self,
        run_at: datetime,
        user_id: int,
        booking_date: datetime,
        class_name: str,
    ) -> str:
        job = self._scheduler.add_job(
            self._handler,
            trigger=DateTrigger(run_date=run_at),
            args=[user_id, booking_date, class_name],
            misfire_grace_time=None,  # always fire even if missed
        )
        return job.id

    def remove_job(self, job_id: str) -> None:
        self._scheduler.remove_job(job_id)
