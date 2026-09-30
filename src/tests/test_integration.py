"""
Integration tests for clean architecture wiring.

Uses real objects for internal components; only external APIs (aimharder.com HTTP,
Telegram API) remain mocked.
"""
import json
import shutil
import time as time_module
from datetime import datetime
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
                }
            ],
            "recurrentBookingGoals": {},
        }
    ]
    dst = tmp_path / "test_schedule.json"
    dst.write_text(json.dumps(data, indent=4))
    return str(dst)


@pytest.fixture
def at_trigger_time():
    """Pin the clock ahead of schedule_file_with_goal's class, or it lapses once 2027 passes."""
    from freezegun import freeze_time

    with freeze_time(datetime(2027, 6, 12, 10, 0)):
        yield


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
    from domain.exceptions import BookingFailed  # noqa: F401


# ── Test 2: schedule → remove roundtrip ──────────────────────────────────────


def test_schedule_then_remove_roundtrip(schedule_file):
    """Real ScheduleBookingUseCase + RemoveBookingUseCase interact with real repo."""
    from infrastructure.persistence.json_repository import JsonRepository
    from infrastructure.aimharder.client_factory import AimHarderClientFactory
    from infrastructure.scheduling.apscheduler import APSchedulerAdapter
    from application.use_cases.schedule_booking import ScheduleBookingUseCase
    from application.use_cases.remove_booking import RemoveBookingUseCase

    from domain.ports.gym_config import IGymConfig
    json_repo = JsonRepository(schedule_file)
    apscheduler = APSchedulerAdapter(on_job_execute=lambda *a: None)
    gym_config = MagicMock(spec=IGymConfig)
    gym_config.booking_trigger_time.side_effect = lambda class_start: class_start
    schedule_uc = ScheduleBookingUseCase(json_repo, json_repo, apscheduler, gym_config)
    remove_uc = RemoveBookingUseCase(json_repo, apscheduler)

    from domain.models import BookingGoal

    class_start = datetime(2027, 6, 15, 10, 0)
    schedule_uc.execute(
        user_id=66666666,
        booking_goal=BookingGoal(class_start=class_start, class_name="WOD"),
    )

    # After scheduling: user has 1 booking goal
    user = json_repo.get_user(66666666)
    assert len(user.booking_goals) == 1
    goal = user.booking_goals[0]
    assert goal.class_name == "WOD"
    assert goal.class_start == class_start


    # After remove: user has 0 booking goals
    remove_uc.execute(66666666, goal)
    user_after = json_repo.get_user(66666666)
    assert len(user_after.booking_goals) == 0


# ── Test 3: startup recovery with real components ─────────────────────────────


def test_startup_recovery_with_real_components(schedule_file_with_goal):
    """Startup recovery re-schedules persisted goals and dedup fires correctly."""
    from infrastructure.persistence.json_repository import JsonRepository
    from infrastructure.aimharder.client_factory import AimHarderClientFactory
    from infrastructure.scheduling.apscheduler import APSchedulerAdapter
    from application.use_cases.schedule_booking import ScheduleBookingUseCase

    from domain.ports.gym_config import IGymConfig
    json_repo = JsonRepository(schedule_file_with_goal)
    apscheduler = APSchedulerAdapter(on_job_execute=lambda *a: None)
    gym_config = MagicMock(spec=IGymConfig)
    gym_config.booking_trigger_time.side_effect = lambda class_start: class_start
    schedule_uc = ScheduleBookingUseCase(json_repo, json_repo, apscheduler, gym_config)

    # Run startup recovery (mirrors main.py bootstrap loop)
    for user in json_repo.get_all_users():
        for goal in user.booking_goals:
            schedule_uc.execute(user_id=user.id, booking_goal=goal)

    # APScheduler should have exactly 1 job scheduled
    jobs = apscheduler._scheduler.get_jobs()
    assert len(jobs) == 1

    # Repo still has exactly 1 goal (dedup fired — not duplicated)
    user = json_repo.get_user(66666666)
    assert len(user.booking_goals) == 1
    assert user.booking_goals[0].class_name == "WOD"


# ── Test 4: execute booking with real repo and mocked HTTP ───────────────────


def test_execute_booking_with_real_repo_mocked_http(
    schedule_file_with_goal, at_trigger_time
):
    """ExecuteBookingUseCase uses real JsonRepository; gym HTTP is mocked."""
    from infrastructure.persistence.json_repository import JsonRepository
    from application.use_cases.execute_booking import ExecuteBookingUseCase
    from domain.models import GymClass
    from domain.ports.gym_client import IGymClientFactory
    from domain.ports.notifier import IUserNotifier

    json_repo = JsonRepository(schedule_file_with_goal)

    mock_client = MagicMock()
    mock_client.get_classes.return_value = [
        GymClass(name="WOD", class_start=datetime(2027, 6, 15, 10, 0))
    ]
    mock_factory = MagicMock(spec=IGymClientFactory)
    mock_factory.create.return_value = mock_client
    mock_user_notifier = MagicMock(spec=IUserNotifier)

    execute_uc = ExecuteBookingUseCase(
        json_repo, json_repo, mock_factory, mock_user_notifier
    )

    class_start = datetime(2027, 6, 15, 10, 0)
    from domain.models import BookingGoal
    execute_uc.execute(66666666, BookingGoal(class_start=class_start, class_name="WOD"))

    # Gym client's book_class was called
    mock_client.book_class.assert_called_once()

    # Booking goal was removed from repo after execution
    user = json_repo.get_user(66666666)
    assert len(user.booking_goals) == 0

    # User was notified
    mock_user_notifier.notify_user.assert_called_once()


# ── Test 5: APScheduler fires execute handler ─────────────────────────────────


def test_apscheduler_fires_execute_handler():
    """Real APSchedulerAdapter fires the handler with correct arguments."""
    from infrastructure.scheduling.apscheduler import APSchedulerAdapter

    from domain.models import BookingGoal
    calls = []

    def mock_handler(user_id, booking_goal):
        calls.append((user_id, booking_goal))

    apscheduler = APSchedulerAdapter(on_job_execute=mock_handler)
    apscheduler.start()

    goal = BookingGoal(class_start=datetime(2027, 6, 15, 10, 0), class_name="WOD")
    try:
        run_at = datetime(2020, 1, 1, 0, 0, 0)  # past timestamp -> fires immediately
        apscheduler.schedule_job(run_at, user_id=66666666, booking_goal=goal)
        time_module.sleep(0.2)
    finally:
        apscheduler._scheduler.shutdown(wait=False)

    assert len(calls) == 1
    assert calls[0] == (66666666, goal)


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


# ── Failed Booking Attempts: member told, goal consumed ──────────────────────

FAILURE_GOAL_START = datetime(2027, 6, 15, 10, 0)
FAILURE_BOX_NAME = "themonkeybox"
FAILURE_AUTH_COOKIE = "amhrdrauth=token; domain=aimharder.com; path=/"


def _failure_execute_uc(schedule_path, send_fn):
    """Real use case, repository, gym client and notifier; only HTTP and Telegram are fakes."""
    from infrastructure.persistence.json_repository import JsonRepository
    from infrastructure.aimharder.client_factory import AimHarderClientFactory
    from infrastructure.aimharder.gym_config import IAimHarderGym
    from infrastructure.telegram.user_notifier import TelegramUserNotifier
    from application.use_cases.execute_booking import ExecuteBookingUseCase

    gym = MagicMock(spec=IAimHarderGym)
    gym.box_id = 9824
    gym.box_name = FAILURE_BOX_NAME
    json_repo = JsonRepository(schedule_path)
    return ExecuteBookingUseCase(
        json_repo,
        json_repo,
        AimHarderClientFactory(gym),
        TelegramUserNotifier(send_fn, sleep=lambda seconds: None),
    )


def _goals_on_disk(schedule_path):
    with open(schedule_path) as f:
        return json.load(f)[0]["bookingGoals"]


def _mock_login_ok(http_mock):
    import responses
    from constants import LOGIN_ENDPOINT

    http_mock.add(
        responses.POST,
        LOGIN_ENDPOINT,
        json={"user": {"id": 1}},
        headers={"Set-Cookie": FAILURE_AUTH_COOKIE},
    )


def _mock_timetable_with_wod(http_mock):
    import responses
    from constants import classes_endpoint

    http_mock.add(
        responses.GET,
        classes_endpoint(FAILURE_BOX_NAME),
        json={"bookings": [{"id": "1", "timeid": "1000_60", "className": "WOD"}]},
    )


def test_rejected_booking_tells_the_member_and_consumes_the_goal(
    schedule_file_with_goal, http_mock, at_trigger_time
):
    import responses
    from constants import book_endpoint
    from domain.exceptions import BookingFailed
    from domain.models import BookingGoal

    _mock_login_ok(http_mock)
    _mock_timetable_with_wod(http_mock)
    http_mock.add(
        responses.POST, book_endpoint(FAILURE_BOX_NAME), json={"errorMssg": "nope"}
    )
    send_fn = MagicMock()
    execute_uc = _failure_execute_uc(schedule_file_with_goal, send_fn)

    with pytest.raises(BookingFailed):
        execute_uc.execute(
            66666666, BookingGoal(class_start=FAILURE_GOAL_START, class_name="WOD")
        )

    send_fn.assert_called_once_with(
        chat_id=66666666,
        message=(
            "❌ Couldn't book WOD\n"
            "📅 15/06/2027 10:00\n"
            "The gym rejected the booking without saying why"
        ),
    )
    assert _goals_on_disk(schedule_file_with_goal) == []


def test_rejected_login_tells_the_member_and_consumes_the_goal(
    schedule_file_with_goal, http_mock, at_trigger_time
):
    import responses
    from constants import LOGIN_ENDPOINT
    from domain.exceptions import AuthenticationFailed
    from domain.models import BookingGoal

    http_mock.add(
        responses.POST,
        LOGIN_ENDPOINT,
        status=401,
        json={"error": {"message": "LOGIN_ERROR_INVALID_CREDENTIALS"}},
    )
    send_fn = MagicMock()
    execute_uc = _failure_execute_uc(schedule_file_with_goal, send_fn)

    with pytest.raises(AuthenticationFailed):
        execute_uc.execute(
            66666666, BookingGoal(class_start=FAILURE_GOAL_START, class_name="WOD")
        )

    send_fn.assert_called_once_with(
        chat_id=66666666,
        message=(
            "❌ Couldn't book WOD\n"
            "📅 15/06/2027 10:00\n"
            "AimBot couldn't sign in to your gym account."
        ),
    )
    assert _goals_on_disk(schedule_file_with_goal) == []


def test_unrecognized_fault_tells_the_member_without_a_stack_trace(
    schedule_file_with_goal, http_mock, at_trigger_time
):
    import responses
    from constants import classes_endpoint
    from domain.models import BookingGoal

    _mock_login_ok(http_mock)
    http_mock.add(
        responses.GET,
        classes_endpoint(FAILURE_BOX_NAME),
        status=502,
        body="<html><body>Bad Gateway</body></html>",
        content_type="text/html",
    )
    send_fn = MagicMock()
    execute_uc = _failure_execute_uc(schedule_file_with_goal, send_fn)

    with pytest.raises(ValueError):
        execute_uc.execute(
            66666666, BookingGoal(class_start=FAILURE_GOAL_START, class_name="WOD")
        )

    send_fn.assert_called_once_with(
        chat_id=66666666,
        message=(
            "❌ Couldn't book WOD\n"
            "📅 15/06/2027 10:00\n"
            "Something went wrong on our side."
        ),
    )
    assert _goals_on_disk(schedule_file_with_goal) == []


def test_lapsed_goal_is_swept_without_an_attempt_or_a_message(
    schedule_file_with_goal, http_mock
):
    from freezegun import freeze_time
    from domain.models import BookingGoal

    send_fn = MagicMock()
    execute_uc = _failure_execute_uc(schedule_file_with_goal, send_fn)

    with freeze_time(datetime(2027, 6, 15, 10, 1)):
        execute_uc.execute(
            66666666, BookingGoal(class_start=FAILURE_GOAL_START, class_name="WOD")
        )

    assert len(http_mock.calls) == 0
    send_fn.assert_not_called()
    assert _goals_on_disk(schedule_file_with_goal) == []


def test_undeliverable_failure_message_still_consumes_the_goal_and_is_loud(
    schedule_file_with_goal, http_mock, at_trigger_time
):
    """Discard comes before notify, so a Telegram outage cannot leave the goal alive."""
    import responses
    from constants import book_endpoint
    from telegram.error import TimedOut
    from domain.exceptions import BookingFailed
    from domain.models import BookingGoal

    _mock_login_ok(http_mock)
    _mock_timetable_with_wod(http_mock)
    http_mock.add(
        responses.POST, book_endpoint(FAILURE_BOX_NAME), json={"errorMssg": "nope"}
    )
    send_fn = MagicMock(side_effect=TimedOut())
    execute_uc = _failure_execute_uc(schedule_file_with_goal, send_fn)

    with pytest.raises(TimedOut) as raised:
        execute_uc.execute(
            66666666, BookingGoal(class_start=FAILURE_GOAL_START, class_name="WOD")
        )

    # The operator's log shows the booking failure chained under the send failure.
    assert isinstance(raised.value.__context__, BookingFailed)
    assert send_fn.call_count == 3
    assert _goals_on_disk(schedule_file_with_goal) == []


def test_undeliverable_confirmation_is_never_reported_as_a_failed_booking(
    schedule_file_with_goal, http_mock, at_trigger_time
):
    """The class is booked; losing the confirmation must not tell the member otherwise."""
    import responses
    from constants import book_endpoint
    from telegram.error import TimedOut
    from domain.models import BookingGoal

    _mock_login_ok(http_mock)
    _mock_timetable_with_wod(http_mock)
    http_mock.add(responses.POST, book_endpoint(FAILURE_BOX_NAME), json={})
    # The confirmation exhausts its retries; any later send would get through.
    send_fn = MagicMock(side_effect=[TimedOut(), TimedOut(), TimedOut(), None])
    execute_uc = _failure_execute_uc(schedule_file_with_goal, send_fn)

    with pytest.raises(TimedOut):
        execute_uc.execute(
            66666666, BookingGoal(class_start=FAILURE_GOAL_START, class_name="WOD")
        )

    sent = [c.kwargs["message"] for c in send_fn.call_args_list]
    assert sent == ["class booked for some-email@gmail.com: WOD 10:00"] * 3
    assert _goals_on_disk(schedule_file_with_goal) == []
