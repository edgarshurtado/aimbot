import pytest
from datetime import datetime

from domain.models import BookingGoal
from domain.ports.booking_repository import IBookingRepository
from domain.ports.scheduler import IJobScheduler
from application.use_cases.remove_booking import RemoveBookingUseCase
from tests.fakes import InMemoryBookingRepository


@pytest.fixture
def booking_repo():
    return InMemoryBookingRepository()


@pytest.fixture
def scheduler(mocker):
    return mocker.Mock(spec=IJobScheduler)


@pytest.fixture
def remove_uc(booking_repo, scheduler):
    return RemoveBookingUseCase(booking_repo, scheduler)


def test_remove_booking_removes_job_and_goal(remove_uc, booking_repo, scheduler):
    goal = BookingGoal(class_start=datetime(2027, 3, 15, 18, 30), class_name="WOD")
    booking_repo.add_booking_goal(123, goal)

    remove_uc.execute(user_id=123, booking_goal=goal)

    scheduler.remove_job.assert_called_once_with(123, goal)
    assert booking_repo.get_user_bookings(123) == []


def test_remove_booking_calls_scheduler_before_repo(mocker):
    goal = BookingGoal(class_start=datetime(2027, 3, 15, 18, 30), class_name="WOD")
    booking_repo = mocker.Mock(spec=IBookingRepository)
    scheduler = mocker.Mock(spec=IJobScheduler)
    uc = RemoveBookingUseCase(booking_repo, scheduler)

    call_order = []
    scheduler.remove_job.side_effect = lambda *a: call_order.append("scheduler")
    booking_repo.remove_booking_goal.side_effect = lambda *a: call_order.append("repo")

    uc.execute(user_id=123, booking_goal=goal)

    assert call_order == ["scheduler", "repo"]


def test_remove_booking_propagates_scheduler_error(booking_repo, scheduler):
    goal = BookingGoal(class_start=datetime(2027, 3, 15, 18, 30), class_name="WOD")
    booking_repo.add_booking_goal(123, goal)
    uc = RemoveBookingUseCase(booking_repo, scheduler)

    scheduler.remove_job.side_effect = Exception("job not found")

    with pytest.raises(Exception, match="job not found"):
        uc.execute(user_id=123, booking_goal=goal)

    assert booking_repo.get_user_bookings(123) == [goal]
