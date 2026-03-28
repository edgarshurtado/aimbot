import inspect
import pytest
from datetime import datetime

from domain.exceptions import UserNotFound
from domain.models import User, BookingGoal
from domain.ports.gym_config import IGymConfig
from domain.ports.scheduler import IJobScheduler
from application.use_cases.schedule_booking import ScheduleBookingUseCase
from tests.fakes import InMemoryBookingRepository, InMemoryUserRepository


@pytest.fixture
def user_repo():
    return InMemoryUserRepository(users=[User(id=123, email="a@b.com", password="pw")])


@pytest.fixture
def booking_repo():
    return InMemoryBookingRepository()


@pytest.fixture
def scheduler(mocker):
    return mocker.Mock(spec=IJobScheduler)


@pytest.fixture
def gym_config(mocker):
    return mocker.Mock(spec=IGymConfig)


@pytest.fixture
def schedule_uc(user_repo, booking_repo, scheduler, gym_config):
    return ScheduleBookingUseCase(user_repo, booking_repo, scheduler, gym_config)


def test_schedule_booking_creates_job_and_persists_goal(
    schedule_uc, booking_repo, scheduler, gym_config
):
    gym_config.booking_trigger_time.return_value = datetime(2027, 3, 12, 18, 30)

    schedule_uc.execute(
        user_id=123, class_start=datetime(2027, 3, 15, 18, 30), class_name="WOD"
    )

    expected_goal = BookingGoal(
        class_start=datetime(2027, 3, 15, 18, 30), class_name="WOD"
    )
    scheduler.schedule_job.assert_called_once_with(
        run_at=datetime(2027, 3, 12, 18, 30),
        user_id=123,
        booking_goal=expected_goal,
    )
    assert booking_repo.get_user_bookings(123) == [expected_goal]


def test_schedule_booking_user_not_found(
    booking_repo, scheduler, gym_config
):
    empty_user_repo = InMemoryUserRepository()
    uc = ScheduleBookingUseCase(empty_user_repo, booking_repo, scheduler, gym_config)

    with pytest.raises(UserNotFound):
        uc.execute(
            user_id=999,
            class_start=datetime(2027, 3, 15, 18, 30),
            class_name="WOD",
        )

    scheduler.schedule_job.assert_not_called()
    assert booking_repo.get_user_bookings(999) == []


def test_schedule_booking_uses_platform_trigger_time(
    schedule_uc, scheduler, gym_config
):
    gym_config.booking_trigger_time.return_value = datetime(2027, 6, 7, 10, 0)

    schedule_uc.execute(
        user_id=123, class_start=datetime(2027, 6, 10, 10, 0), class_name="WOD"
    )

    scheduler.schedule_job.assert_called_once()
    call_kwargs = scheduler.schedule_job.call_args
    assert call_kwargs.kwargs["run_at"] == datetime(2027, 6, 7, 10, 0)

    gym_config.booking_trigger_time.assert_called_once_with(
        datetime(2027, 6, 10, 10, 0)
    )


def test_schedule_booking_does_not_depend_on_execute_use_case():
    sig = inspect.signature(ScheduleBookingUseCase.__init__)
    param_names = list(sig.parameters.keys())
    assert not any("execute" in p.lower() for p in param_names)
