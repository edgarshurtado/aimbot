import time
import pytest
from datetime import datetime

from apscheduler.triggers.date import DateTrigger
from domain.ports.scheduler import IJobScheduler
from infrastructure.scheduling.apscheduler import APSchedulerAdapter


@pytest.fixture
def adapter(mocker):
    handler = mocker.Mock()
    return APSchedulerAdapter(on_job_execute=handler), handler


def test_implements_ischeduler(adapter):
    a, _ = adapter
    assert isinstance(a, IJobScheduler)


def test_schedule_job_creates_date_trigger(adapter):
    a, _ = adapter
    a.schedule_job(
        run_at=datetime(2027, 3, 12, 18, 30),
        user_id=123,
        booking_date=datetime(2027, 3, 15, 18, 30),
        class_name="WOD",
    )
    jobs = a._scheduler.get_jobs()
    assert len(jobs) == 1
    assert isinstance(jobs[0].trigger, DateTrigger)


def test_scheduled_job_calls_handler_with_correct_args(mocker):
    """Schedule with a past run_at, start scheduler, verify handler called."""
    handler = mocker.Mock()
    a = APSchedulerAdapter(on_job_execute=handler)

    booking_date = datetime(2027, 3, 15, 18, 30)
    a.schedule_job(
        run_at=datetime(2020, 1, 1, 0, 0),  # in the past → fires immediately
        user_id=123,
        booking_date=booking_date,
        class_name="WOD",
    )
    a.start()
    time.sleep(0.2)  # give scheduler time to fire

    handler.assert_called_once_with(123, booking_date, "WOD")
    a._scheduler.shutdown(wait=False)


def test_remove_job_removes_scheduled_job(adapter):
    from apscheduler.jobstores.base import JobLookupError
    a, _ = adapter
    a.schedule_job(
        run_at=datetime(2027, 3, 12, 18, 30),
        user_id=123,
        booking_date=datetime(2027, 3, 15, 18, 30),
        class_name="WOD",
    )
    a.remove_job(123, datetime(2027, 3, 15, 18, 30), "WOD")

    with pytest.raises(JobLookupError):
        a.remove_job(123, datetime(2027, 3, 15, 18, 30), "WOD")


def test_start_starts_scheduler(mocker):
    handler = mocker.Mock()
    a = APSchedulerAdapter(on_job_execute=handler)
    mock_start = mocker.patch.object(a._scheduler, "start")
    a.start()
    mock_start.assert_called_once()


def test_schedule_job_different_bookings_create_separate_jobs(adapter):
    a, _ = adapter
    a.schedule_job(
        run_at=datetime(2027, 3, 12, 18, 30),
        user_id=1,
        booking_date=datetime(2027, 3, 15, 18, 30),
        class_name="WOD",
    )
    a.schedule_job(
        run_at=datetime(2027, 3, 13, 10, 0),
        user_id=2,
        booking_date=datetime(2027, 3, 16, 10, 0),
        class_name="OPEN",
    )
    assert len(a._scheduler.get_jobs()) == 2
