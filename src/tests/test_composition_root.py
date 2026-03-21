"""
Tests for the composition root (main.py bootstrap logic).

main.py must expose a bootstrap() function that:
1. Creates all real objects (with injected dependencies for testability)
2. Runs startup recovery (re-schedules persisted booking goals)
3. Returns the key wired objects for verification
"""
import pytest
from datetime import datetime

from domain.models import BookingGoal, User
from main import bootstrap


@pytest.fixture
def mocked_bootstrap(mocker):
    """
    Patch all external dependencies and return mock objects + bootstrap result.
    """
    # Patch infrastructure classes
    mock_repo_cls = mocker.patch("main.JsonRepository")
    mock_factory_cls = mocker.patch("main.AimHarderClientFactory")
    mock_bot_cls = mocker.patch("main.TelegramBot")
    mocker.patch("main.TelegramUserNotifier")
    mocker.patch("main.TelegramGroupNotifier")
    mock_execute_uc_cls = mocker.patch("main.ExecuteBookingUseCase")
    mock_apscheduler_cls = mocker.patch("main.APSchedulerAdapter")
    mock_schedule_uc_cls = mocker.patch("main.ScheduleBookingUseCase")
    mocker.patch("main.RemoveBookingUseCase")

    # Configure mock instances
    mock_repo = mock_repo_cls.return_value
    mock_factory = mock_factory_cls.return_value
    mock_bot = mock_bot_cls.return_value
    mock_execute_uc = mock_execute_uc_cls.return_value
    mock_apscheduler = mock_apscheduler_cls.return_value
    mock_schedule_uc = mock_schedule_uc_cls.return_value

    # Default: no users
    mock_repo.get_all_users.return_value = []

    result = bootstrap()

    return {
        "result": result,
        "repo": mock_repo,
        "factory": mock_factory,
        "bot": mock_bot,
        "execute_uc": mock_execute_uc,
        "apscheduler": mock_apscheduler,
        "schedule_uc": mock_schedule_uc,
        "schedule_uc_cls": mock_schedule_uc_cls,
        "apscheduler_cls": mock_apscheduler_cls,
        "execute_uc_cls": mock_execute_uc_cls,
    }


def test_startup_recovery_no_users(mocker):
    mocker.patch("main.JsonRepository")
    mocker.patch("main.AimHarderClientFactory")
    mocker.patch("main.TelegramBot")
    mocker.patch("main.TelegramUserNotifier")
    mocker.patch("main.TelegramGroupNotifier")
    mocker.patch("main.ExecuteBookingUseCase")
    mocker.patch("main.APSchedulerAdapter")
    mock_schedule_uc_cls = mocker.patch("main.ScheduleBookingUseCase")
    mocker.patch("main.RemoveBookingUseCase")

    repo = mocker.patch("main.JsonRepository").return_value
    repo.get_all_users.return_value = []

    bootstrap()

    # schedule_uc.execute should NOT be called (no users, no goals)
    schedule_uc = mock_schedule_uc_cls.return_value
    schedule_uc.execute.assert_not_called()


def test_startup_recovery_reschedules_all_user_goals(mocker):
    mocker.patch("main.AimHarderClientFactory")
    mocker.patch("main.TelegramBot")
    mocker.patch("main.TelegramUserNotifier")
    mocker.patch("main.TelegramGroupNotifier")
    mocker.patch("main.ExecuteBookingUseCase")
    mocker.patch("main.APSchedulerAdapter")
    mock_schedule_uc_cls = mocker.patch("main.ScheduleBookingUseCase")
    mocker.patch("main.RemoveBookingUseCase")
    mock_repo_cls = mocker.patch("main.JsonRepository")

    mock_repo = mock_repo_cls.return_value
    mock_repo.get_all_users.return_value = [
        User(
            id=1,
            email="a@b.com",
            password="pw",
            booking_goals=[
                BookingGoal(
                    booking_date=datetime(2027, 3, 15, 18, 30),
                    name="WOD",
                )
            ],
        )
    ]

    bootstrap()

    schedule_uc = mock_schedule_uc_cls.return_value
    schedule_uc.execute.assert_called_once_with(
        user_id=1,
        booking_date=datetime(2027, 3, 15, 18, 30),
        class_name="WOD",
    )


def test_startup_recovery_multiple_users(mocker):
    mocker.patch("main.AimHarderClientFactory")
    mocker.patch("main.TelegramBot")
    mocker.patch("main.TelegramUserNotifier")
    mocker.patch("main.TelegramGroupNotifier")
    mocker.patch("main.ExecuteBookingUseCase")
    mocker.patch("main.APSchedulerAdapter")
    mock_schedule_uc_cls = mocker.patch("main.ScheduleBookingUseCase")
    mocker.patch("main.RemoveBookingUseCase")
    mock_repo_cls = mocker.patch("main.JsonRepository")

    mock_repo = mock_repo_cls.return_value
    mock_repo.get_all_users.return_value = [
        User(
            id=1,
            email="a@b.com",
            password="pw",
            booking_goals=[
                BookingGoal(booking_date=datetime(2027, 3, 15, 18, 30), name="WOD"),
                BookingGoal(booking_date=datetime(2027, 3, 16, 10, 0), name="OPEN"),
            ],
        ),
        User(
            id=2,
            email="b@c.com",
            password="pw2",
            booking_goals=[
                BookingGoal(booking_date=datetime(2027, 3, 17, 9, 0), name="GYMNASTIC"),
            ],
        ),
    ]

    bootstrap()

    schedule_uc = mock_schedule_uc_cls.return_value
    assert schedule_uc.execute.call_count == 3


def test_apscheduler_start_called(mocker):
    mocker.patch("main.JsonRepository").return_value.get_all_users.return_value = []
    mocker.patch("main.AimHarderClientFactory")
    mocker.patch("main.TelegramBot")
    mocker.patch("main.TelegramUserNotifier")
    mocker.patch("main.TelegramGroupNotifier")
    mocker.patch("main.ExecuteBookingUseCase")
    mock_apscheduler_cls = mocker.patch("main.APSchedulerAdapter")
    mocker.patch("main.ScheduleBookingUseCase")
    mocker.patch("main.RemoveBookingUseCase")

    bootstrap()

    mock_apscheduler = mock_apscheduler_cls.return_value
    mock_apscheduler.start.assert_called_once()


def test_execute_uc_wired_as_job_handler(mocker):
    """APSchedulerAdapter must be constructed with execute_uc.execute as on_job_execute."""
    mocker.patch("main.JsonRepository").return_value.get_all_users.return_value = []
    mocker.patch("main.AimHarderClientFactory")
    mocker.patch("main.TelegramBot")
    mocker.patch("main.TelegramUserNotifier")
    mocker.patch("main.TelegramGroupNotifier")
    mock_execute_uc_cls = mocker.patch("main.ExecuteBookingUseCase")
    mock_apscheduler_cls = mocker.patch("main.APSchedulerAdapter")
    mocker.patch("main.ScheduleBookingUseCase")
    mocker.patch("main.RemoveBookingUseCase")

    bootstrap()

    mock_execute_uc = mock_execute_uc_cls.return_value
    call_kwargs = mock_apscheduler_cls.call_args.kwargs
    assert call_kwargs.get("on_job_execute") == mock_execute_uc.execute
