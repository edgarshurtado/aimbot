import inspect
import pytest
from datetime import datetime

from domain.models import User, BookingGoal
from domain.ports.booking_repository import IBookingRepository
from domain.ports.gym_config import IGymConfig
from domain.ports.scheduler import IJobScheduler
from domain.ports.user_repository import IUserRepository
from application.use_cases.schedule_booking import ScheduleBookingUseCase


@pytest.fixture
def schedule_booking(mocker):
    user_repo = mocker.Mock(spec=IUserRepository)
    booking_repo = mocker.Mock(spec=IBookingRepository)
    scheduler = mocker.Mock(spec=IJobScheduler)
    gym_config = mocker.Mock(spec=IGymConfig)
    uc = ScheduleBookingUseCase(user_repo, booking_repo, scheduler, gym_config)
    return uc, user_repo, booking_repo, scheduler, gym_config


def test_schedule_booking_creates_job_and_persists_goal(schedule_booking):
    uc, user_repo, booking_repo, scheduler, gym_config = schedule_booking

    user_repo.get_user.return_value = User(id=123, email="a@b.com", password="pw")
    gym_config.booking_trigger_time.return_value = datetime(2027, 3, 12, 18, 30)

    uc.execute(user_id=123, class_start=datetime(2027, 3, 15, 18, 30), class_name="WOD")

    scheduler.schedule_job.assert_called_once_with(
        run_at=datetime(2027, 3, 12, 18, 30),
        user_id=123,
        class_start=datetime(2027, 3, 15, 18, 30),
        class_name="WOD",
    )
    booking_repo.add_booking_goal.assert_called_once_with(
        123,
        BookingGoal(
            class_start=datetime(2027, 3, 15, 18, 30),
            class_name="WOD",
        ),
    )


def test_schedule_booking_user_not_found(schedule_booking):
    uc, user_repo, booking_repo, scheduler, gym_config = schedule_booking

    user_repo.get_user.return_value = None

    with pytest.raises(Exception):
        uc.execute(user_id=999, class_start=datetime(2027, 3, 15, 18, 30), class_name="WOD")

    scheduler.schedule_job.assert_not_called()
    booking_repo.add_booking_goal.assert_not_called()


def test_schedule_booking_uses_platform_trigger_time(schedule_booking):
    uc, user_repo, booking_repo, scheduler, gym_config = schedule_booking

    user_repo.get_user.return_value = User(id=1, email="a@b.com", password="pw")
    gym_config.booking_trigger_time.return_value = datetime(2027, 6, 7, 10, 0)

    uc.execute(user_id=1, class_start=datetime(2027, 6, 10, 10, 0), class_name="WOD")

    scheduler.schedule_job.assert_called_once()
    call_kwargs = scheduler.schedule_job.call_args
    assert call_kwargs.kwargs["run_at"] == datetime(2027, 6, 7, 10, 0)

    gym_config.booking_trigger_time.assert_called_once_with(datetime(2027, 6, 10, 10, 0))


def test_schedule_booking_does_not_depend_on_execute_use_case():
    sig = inspect.signature(ScheduleBookingUseCase.__init__)
    param_names = list(sig.parameters.keys())
    assert not any("execute" in p.lower() for p in param_names)
