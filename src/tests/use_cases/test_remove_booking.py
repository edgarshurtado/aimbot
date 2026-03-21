import pytest
from datetime import datetime

from domain.ports.booking_repository import IBookingRepository
from domain.ports.scheduler import IJobScheduler
from application.use_cases.remove_booking import RemoveBookingUseCase


@pytest.fixture
def remove_booking(mocker):
    booking_repo = mocker.Mock(spec=IBookingRepository)
    scheduler = mocker.Mock(spec=IJobScheduler)
    uc = RemoveBookingUseCase(booking_repo, scheduler)
    return uc, booking_repo, scheduler


def test_remove_booking_removes_job_and_goal(remove_booking):
    uc, booking_repo, scheduler = remove_booking
    booking_date = datetime(2027, 3, 15, 18, 30)

    uc.execute(user_id=123, booking_date=booking_date, class_name="WOD")

    scheduler.remove_job.assert_called_once_with(123, booking_date, "WOD")
    booking_repo.remove_booking_goal.assert_called_once_with(123, booking_date, "WOD")


def test_remove_booking_calls_scheduler_before_repo(remove_booking):
    uc, booking_repo, scheduler = remove_booking

    call_order = []
    scheduler.remove_job.side_effect = lambda *a: call_order.append("scheduler")
    booking_repo.remove_booking_goal.side_effect = lambda *a: call_order.append("repo")

    uc.execute(user_id=123, booking_date=datetime(2027, 3, 15, 18, 30), class_name="WOD")

    assert call_order == ["scheduler", "repo"]


def test_remove_booking_propagates_scheduler_error(remove_booking):
    uc, booking_repo, scheduler = remove_booking

    scheduler.remove_job.side_effect = Exception("job not found")

    with pytest.raises(Exception, match="job not found"):
        uc.execute(user_id=123, booking_date=datetime(2027, 3, 15, 18, 30), class_name="WOD")

    booking_repo.remove_booking_goal.assert_not_called()
