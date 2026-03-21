"""
Integration tests for clean architecture wiring.

Uses real objects for internal components; only external APIs (aimharder.com HTTP,
Telegram API) remain mocked.
"""
import json
import shutil
import time as time_module
from datetime import datetime, time
from unittest.mock import MagicMock

import pytest


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def schedule_file(tmp_path):
    """Copy test_schedule.json to a temp file and return the absolute path."""
    src = "src/tests/test_schedule.json"
    dst = tmp_path / "test_schedule.json"
    shutil.copy(src, dst)
    return str(dst)


@pytest.fixture
def schedule_file_with_goal(tmp_path):
    """Temp schedule file seeded with user 66666666 having 1 booking goal."""
    data = [
        {
            "user": {
                "email": "some-email@gmail.com",
                "password": "password",
                "id": 66666666,
            },
            "bookingGoals": [
                {
                    "datetime": "15-06-2027 10:00",
                    "name": "WOD",
                    "job_id": "seed-job-001",
                }
            ],
            "recurrentBookingGoals": {},
        }
    ]
    dst = tmp_path / "test_schedule.json"
    dst.write_text(json.dumps(data, indent=4))
    return str(dst)


# ── Test 1: no import errors ──────────────────────────────────────────────────


def test_full_wiring_no_import_errors():
    """All production modules import without error or circular imports."""
    from infrastructure.persistence.json_repository import JsonRepository  # noqa: F401
    from infrastructure.aimharder.client_factory import AimHarderClientFactory  # noqa: F401
    from infrastructure.scheduling.apscheduler import APSchedulerAdapter  # noqa: F401
    from infrastructure.telegram.group_notifier import TelegramGroupNotifier  # noqa: F401
    from infrastructure.telegram.user_notifier import TelegramUserNotifier  # noqa: F401
    from application.use_cases.schedule_booking import ScheduleBookingUseCase  # noqa: F401
    from application.use_cases.execute_booking import ExecuteBookingUseCase  # noqa: F401
    from application.use_cases.remove_booking import RemoveBookingUseCase  # noqa: F401
    from domain.models import GymClass, BookingGoal, User  # noqa: F401
    from domain.exceptions import BoxClosed, NoBookingGoal  # noqa: F401


# ── Test 2: schedule → remove roundtrip ──────────────────────────────────────


def test_schedule_then_remove_roundtrip(schedule_file):
    """Real ScheduleBookingUseCase + RemoveBookingUseCase interact with real repo."""
    from infrastructure.persistence.json_repository import JsonRepository
    from infrastructure.aimharder.client_factory import AimHarderClientFactory
    from infrastructure.scheduling.apscheduler import APSchedulerAdapter
    from application.use_cases.schedule_booking import ScheduleBookingUseCase
    from application.use_cases.remove_booking import RemoveBookingUseCase

    json_repo = JsonRepository(schedule_file)
    apscheduler = APSchedulerAdapter(on_job_execute=lambda *a: None)
    factory = AimHarderClientFactory(box_id=1, box_name="test-box")
    schedule_uc = ScheduleBookingUseCase(json_repo, json_repo, apscheduler, factory)
    remove_uc = RemoveBookingUseCase(json_repo, apscheduler)

    booking_date = datetime(2027, 6, 15, 10, 0)
    schedule_uc.execute(user_id=66666666, booking_date=booking_date, class_name="WOD")

    # After scheduling: user has 1 booking goal
    user = json_repo.get_user(66666666)
    assert len(user.booking_goals) == 1
    goal = user.booking_goals[0]
    assert goal.name == "WOD"
    assert goal.booking_date == booking_date
    assert goal.job_id  # job_id was assigned by the scheduler

    # After remove: user has 0 booking goals
    remove_uc.execute(66666666, goal.job_id)
    user_after = json_repo.get_user(66666666)
    assert len(user_after.booking_goals) == 0


# ── Test 3: startup recovery with real components ─────────────────────────────


def test_startup_recovery_with_real_components(schedule_file_with_goal):
    """Startup recovery re-schedules persisted goals and dedup fires correctly."""
    from infrastructure.persistence.json_repository import JsonRepository
    from infrastructure.aimharder.client_factory import AimHarderClientFactory
    from infrastructure.scheduling.apscheduler import APSchedulerAdapter
    from application.use_cases.schedule_booking import ScheduleBookingUseCase

    json_repo = JsonRepository(schedule_file_with_goal)
    apscheduler = APSchedulerAdapter(on_job_execute=lambda *a: None)
    factory = AimHarderClientFactory(box_id=1, box_name="test-box")
    schedule_uc = ScheduleBookingUseCase(json_repo, json_repo, apscheduler, factory)

    # Run startup recovery (mirrors main.py bootstrap loop)
    for user in json_repo.get_all_users():
        for goal in user.booking_goals:
            schedule_uc.execute(
                user_id=user.id,
                booking_date=goal.booking_date,
                class_name=goal.name,
            )

    # APScheduler should have exactly 1 job scheduled
    jobs = apscheduler._scheduler.get_jobs()
    assert len(jobs) == 1

    # Repo still has exactly 1 goal (dedup fired — job_id updated, not duplicated)
    user = json_repo.get_user(66666666)
    assert len(user.booking_goals) == 1
    assert user.booking_goals[0].name == "WOD"


# ── Test 4: execute booking with real repo and mocked HTTP ───────────────────


def test_execute_booking_with_real_repo_mocked_http(schedule_file_with_goal):
    """ExecuteBookingUseCase uses real JsonRepository; gym HTTP is mocked."""
    from infrastructure.persistence.json_repository import JsonRepository
    from application.use_cases.execute_booking import ExecuteBookingUseCase
    from domain.models import GymClass
    from domain.ports.gym_client import IGymClientFactory
    from domain.ports.notifier import IUserNotifier, IGroupNotifier

    json_repo = JsonRepository(schedule_file_with_goal)

    mock_client = MagicMock()
    mock_client.get_classes.return_value = [
        GymClass(id="42", name="WOD", start_time=time(10, 0), spots_available=5, max_spots=20)
    ]
    mock_factory = MagicMock(spec=IGymClientFactory)
    mock_factory.create.return_value = mock_client
    mock_user_notifier = MagicMock(spec=IUserNotifier)
    mock_group_notifier = MagicMock(spec=IGroupNotifier)

    execute_uc = ExecuteBookingUseCase(
        json_repo, json_repo, mock_factory, mock_user_notifier, mock_group_notifier
    )

    booking_date = datetime(2027, 6, 15, 10, 0)
    execute_uc.execute(66666666, booking_date, "WOD")

    # Gym client's book_class was called
    mock_client.book_class.assert_called_once()

    # Booking goal was removed from repo after execution
    user = json_repo.get_user(66666666)
    assert len(user.booking_goals) == 0

    # Notifiers were invoked
    mock_user_notifier.notify_user.assert_called_once()
    mock_group_notifier.notify_group.assert_called_once()


# ── Test 5: APScheduler fires execute handler ─────────────────────────────────


def test_apscheduler_fires_execute_handler():
    """Real APSchedulerAdapter fires the handler with correct arguments."""
    from infrastructure.scheduling.apscheduler import APSchedulerAdapter

    calls = []

    def mock_handler(user_id, booking_date, class_name):
        calls.append((user_id, booking_date, class_name))

    apscheduler = APSchedulerAdapter(on_job_execute=mock_handler)
    apscheduler.start()

    try:
        run_at = datetime(2020, 1, 1, 0, 0, 0)  # past timestamp → fires immediately
        booking_date = datetime(2027, 6, 15, 10, 0)
        apscheduler.schedule_job(
            run_at, user_id=66666666, booking_date=booking_date, class_name="WOD"
        )
        time_module.sleep(0.2)
    finally:
        apscheduler._scheduler.shutdown(wait=False)

    assert len(calls) == 1
    assert calls[0] == (66666666, booking_date, "WOD")


# ── Test 6: path resolution from infrastructure location ─────────────────────


def test_json_repository_path_from_infrastructure_location():
    """JsonRepository('tests/test_schedule.json') resolves correctly from infrastructure/persistence/."""
    from infrastructure.persistence.json_repository import JsonRepository

    repo = JsonRepository("tests/test_schedule.json")

    users = repo.get_all_users()
    assert isinstance(users, list)
    assert len(users) >= 1

    user = repo.get_user(66666666)
    assert user is not None
    assert user.email == "some-email@gmail.com"
