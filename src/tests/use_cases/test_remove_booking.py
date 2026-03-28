import pytest
from datetime import datetime

from domain.models import BookingGoal
from domain.ports.scheduler import IJobScheduler
from application.use_cases.remove_booking import RemoveBookingUseCase
from tests.fakes import InMemoryBookingRepository


DEFAULT_USER_ID = 123


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
    booking_repo.add_booking_goal(DEFAULT_USER_ID, goal)

    remove_uc.execute(user_id=DEFAULT_USER_ID, booking_goal=goal)

    scheduler.remove_job.assert_called_once_with(DEFAULT_USER_ID, goal)
    assert booking_repo.get_user_bookings(DEFAULT_USER_ID) == []


def test_remove_booking_cleans_up_goal_even_if_scheduler_fails(booking_repo, scheduler):
    goal = BookingGoal(class_start=datetime(2027, 3, 15, 18, 30), class_name="WOD")
    booking_repo.add_booking_goal(DEFAULT_USER_ID, goal)
    uc = RemoveBookingUseCase(booking_repo, scheduler)

    scheduler.remove_job.side_effect = Exception("job not found")

    uc.execute(user_id=DEFAULT_USER_ID, booking_goal=goal)

    assert booking_repo.get_user_bookings(DEFAULT_USER_ID) == []
