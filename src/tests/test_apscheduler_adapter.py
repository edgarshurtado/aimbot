import time
import pytest
from datetime import datetime

from apscheduler.triggers.date import DateTrigger
from domain.models import BookingGoal
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
    goal = BookingGoal(class_start=datetime(2027, 3, 15, 18, 30), class_name="WOD")
    a.schedule_job(
        run_at=datetime(2027, 3, 12, 18, 30),
        user_id=123,
        booking_goal=goal,
    )
    jobs = a._scheduler.get_jobs()
    assert len(jobs) == 1
    assert isinstance(jobs[0].trigger, DateTrigger)


def test_scheduled_job_calls_handler_with_correct_args(mocker):
    """Schedule with a past run_at, start scheduler, verify handler called."""
    handler = mocker.Mock()
    a = APSchedulerAdapter(on_job_execute=handler)

    goal = BookingGoal(class_start=datetime(2027, 3, 15, 18, 30), class_name="WOD")
    a.schedule_job(
        run_at=datetime(2020, 1, 1, 0, 0),  # in the past -> fires immediately
        user_id=123,
        booking_goal=goal,
    )
    a.start()
    time.sleep(0.2)  # give scheduler time to fire

    handler.assert_called_once_with(123, goal)
    a._scheduler.shutdown(wait=False)


def test_remove_job_removes_scheduled_job(adapter):
    from apscheduler.jobstores.base import JobLookupError
    a, _ = adapter
    goal = BookingGoal(class_start=datetime(2027, 3, 15, 18, 30), class_name="WOD")
    a.schedule_job(
        run_at=datetime(2027, 3, 12, 18, 30),
        user_id=123,
        booking_goal=goal,
    )
    a.remove_job(123, goal)

    with pytest.raises(JobLookupError):
        a.remove_job(123, goal)


def test_start_starts_scheduler(mocker):
    handler = mocker.Mock()
    a = APSchedulerAdapter(on_job_execute=handler)
    mock_start = mocker.patch.object(a._scheduler, "start")
    a.start()
    mock_start.assert_called_once()


def test_scheduling_the_same_goal_twice_leaves_one_job(adapter):
    """Re-scheduling a goal must be a no-op, not a crash.

    JsonRepository already treats a repeated goal as harmless, but the scheduler
    goes first — so without this the member scrolling back and tapping an old
    class button gets a ConflictingIdError reported as a failure.
    """
    a, _ = adapter
    goal = BookingGoal(class_start=datetime(2027, 3, 15, 18, 30), class_name="WOD")
    a.start()  # a running scheduler enforces job-id uniqueness; a pending one does not

    try:
        a.schedule_job(
            run_at=datetime(2027, 3, 12, 18, 30), user_id=123, booking_goal=goal
        )
        a.schedule_job(
            run_at=datetime(2027, 3, 12, 18, 30), user_id=123, booking_goal=goal
        )

        assert len(a._scheduler.get_jobs()) == 1
    finally:
        a._scheduler.shutdown(wait=False)


def test_schedule_job_different_bookings_create_separate_jobs(adapter):
    a, _ = adapter
    goal1 = BookingGoal(class_start=datetime(2027, 3, 15, 18, 30), class_name="WOD")
    goal2 = BookingGoal(class_start=datetime(2027, 3, 16, 10, 0), class_name="OPEN")
    a.schedule_job(
        run_at=datetime(2027, 3, 12, 18, 30),
        user_id=1,
        booking_goal=goal1,
    )
    a.schedule_job(
        run_at=datetime(2027, 3, 13, 10, 0),
        user_id=2,
        booking_goal=goal2,
    )
    assert len(a._scheduler.get_jobs()) == 2
