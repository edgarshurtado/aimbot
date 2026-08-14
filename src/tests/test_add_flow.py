"""
Integration tests for /add offering the day's real Timetable.

Real repository, real scheduler, real use cases, real bot handlers. Only the two
process edges are mocked: aimharder over HTTP (``responses``) and the Telegram
application.
"""
import json
from datetime import datetime
from unittest.mock import AsyncMock

import pytest
import responses as rsps_lib

from constants import LOGIN_ENDPOINT, classes_endpoint
from domain.ports.gym_config import IGymConfig
from application.use_cases.list_day_classes import ListDayClassesUseCase
from application.use_cases.schedule_booking import ScheduleBookingUseCase
from application.use_cases.remove_booking import RemoveBookingUseCase
from infrastructure.aimharder.client_factory import AimHarderClientFactory
from infrastructure.aimharder.gym_config import IAimHarderGym
from infrastructure.persistence.json_repository import JsonRepository
from infrastructure.scheduling.apscheduler import APSchedulerAdapter
from infrastructure.telegram.bot import TelegramBot

USER_ID = 66666666
BOX_NAME = "themonkeybox"
BOX_ID = 9824
AUTH_COOKIE_HEADER = (
    "amhrdrauth=session-token-abc123; expires=Wed, 01 Jan 2028 00:00:00 GMT;"
    " domain=aimharder.com; path=/; secure; HttpOnly"
)

# The day the member taps, and the day whose Timetable is fetched.
SELECTED_DAY = datetime(2027, 6, 15)
DAY_BUTTON = "15-06 (Tuesday)"


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def schedule_file(tmp_path):
    data = [
        {
            "user": {
                "email": "some-email@gmail.com",
                "password": "password",
                "id": USER_ID,
            },
            "bookingGoals": [],
            "recurrentBookingGoals": {},
        }
    ]
    dst = tmp_path / "test_schedule.json"
    dst.write_text(json.dumps(data, indent=4))
    return str(dst)


@pytest.fixture
def wiring(schedule_file, mocker):
    """The real composition, with only Telegram's Application faked out."""
    mock_builder = mocker.Mock()
    mock_builder.token.return_value = mock_builder
    mock_builder.build.return_value = mocker.Mock()
    mocker.patch("infrastructure.telegram.bot.ApplicationBuilder", return_value=mock_builder)
    mocker.patch("infrastructure.telegram.bot.get_telegram_token", return_value="test-token")

    gym = mocker.Mock(spec=IAimHarderGym)
    gym.box_id = BOX_ID
    gym.box_name = BOX_NAME
    gym.days_in_advance = 3

    gym_config = mocker.Mock(spec=IGymConfig)
    gym_config.booking_trigger_time.side_effect = lambda class_start: class_start

    json_repo = JsonRepository(schedule_file)
    factory = AimHarderClientFactory(gym=gym)
    apscheduler = APSchedulerAdapter(on_job_execute=lambda *a: None)

    bot = TelegramBot(user_repo=json_repo)
    bot.set_use_cases(
        ScheduleBookingUseCase(json_repo, json_repo, apscheduler, gym_config),
        RemoveBookingUseCase(json_repo, apscheduler),
        ListDayClassesUseCase(json_repo, factory),
    )
    return bot, json_repo, apscheduler


def _update(mocker, text=None, callback_data=None):
    update = mocker.Mock()
    update.effective_user.id = USER_ID
    update.effective_chat.id = USER_ID
    update.message = mocker.Mock()
    update.message.text = text
    if callback_data is None:
        update.callback_query = None
    else:
        update.callback_query = AsyncMock()
        update.callback_query.data = callback_data
    return update


def _context(mocker, user_data=None):
    context = mocker.Mock()
    context.bot = AsyncMock()
    context.args = []
    context.user_data = user_data if user_data is not None else {}
    return context


def _sent_texts(context):
    return [c.kwargs.get("text", "") for c in context.bot.send_message.call_args_list]


def _mock_login_success(http_mock):
    http_mock.add(
        rsps_lib.POST,
        LOGIN_ENDPOINT,
        json={"user": {"id": 1}},
        headers={"Set-Cookie": AUTH_COOKIE_HEADER},
    )


def _mock_timetable(http_mock, bookings):
    http_mock.add(rsps_lib.GET, classes_endpoint(BOX_NAME), json={"bookings": bookings})


def _booking(id_, timeid, class_name):
    return {
        "id": id_,
        "timeid": timeid,
        "className": class_name,
        "ocupation": 5,
        "limit": 20,
    }


async def _pick_day(bot, mocker, context):
    update = _update(mocker, text=DAY_BUTTON)
    state = await bot._TelegramBot__day_selected_handler(update, context)
    return state


async def _tap_class(bot, mocker, context, index):
    update = _update(mocker, callback_data=str(index))
    state = await bot._TelegramBot__class_selected_handler(update, context)
    return state, update


# ── The keyboard is built from the real Timetable ─────────────────────────────


@pytest.mark.asyncio
async def test_day_selection_offers_one_button_per_published_class(
    wiring, http_mock, mocker
):
    bot, _, _ = wiring
    _mock_login_success(http_mock)
    _mock_timetable(
        http_mock,
        [
            _booking("2", "1830_60", "WOD"),
            _booking("1", "0730_60", "OPEN"),
            _booking("3", "1830_60", "GYMNASTIC"),
        ],
    )
    context = _context(mocker)

    await _pick_day(bot, mocker, context)

    markup = context.bot.send_message.call_args.kwargs["reply_markup"]
    labels = [row[0].text for row in markup.inline_keyboard]
    assert labels == ["07:30 OPEN", "18:30 GYMNASTIC", "18:30 WOD"]


@pytest.mark.asyncio
async def test_tapping_a_class_persists_the_timetables_exact_name(
    wiring, http_mock, mocker
):
    """The stored name is the platform's, byte for byte — not a member's guess."""
    bot, json_repo, apscheduler = wiring
    _mock_login_success(http_mock)
    _mock_timetable(http_mock, [_booking("2", "1830_60", "WOD KIDS")])
    context = _context(mocker)

    await _pick_day(bot, mocker, context)
    await _tap_class(bot, mocker, context, 0)

    goals = json_repo.get_user(USER_ID).booking_goals
    assert len(goals) == 1
    assert goals[0].class_name == "WOD KIDS"
    assert goals[0].class_start == datetime(2027, 6, 15, 18, 30)
    assert len(apscheduler._scheduler.get_jobs()) == 1


@pytest.mark.asyncio
async def test_tapping_a_class_clears_the_buttons(wiring, http_mock, mocker):
    bot, _, _ = wiring
    _mock_login_success(http_mock)
    _mock_timetable(http_mock, [_booking("2", "1830_60", "WOD")])
    context = _context(mocker)

    await _pick_day(bot, mocker, context)
    _, update = await _tap_class(bot, mocker, context, 0)

    update.callback_query.edit_message_reply_markup.assert_awaited_once_with(
        reply_markup=None
    )


# ── Nothing is offered that the bot could not fetch ───────────────────────────


@pytest.mark.asyncio
async def test_empty_timetable_ends_the_conversation_without_scheduling(
    wiring, http_mock, mocker
):
    from telegram.ext import ConversationHandler

    bot, json_repo, apscheduler = wiring
    _mock_login_success(http_mock)
    _mock_timetable(http_mock, [])
    context = _context(mocker)

    state = await _pick_day(bot, mocker, context)

    assert state == ConversationHandler.END
    assert "No classes published" in _sent_texts(context)[-1]
    assert json_repo.get_user(USER_ID).booking_goals == []
    assert apscheduler._scheduler.get_jobs() == []


@pytest.mark.asyncio
async def test_rejected_credentials_end_the_conversation(wiring, http_mock, mocker):
    from telegram.ext import ConversationHandler

    bot, json_repo, _ = wiring
    http_mock.add(
        rsps_lib.POST,
        LOGIN_ENDPOINT,
        status=401,
        json={"error": {"code": 401, "message": "LOGIN_ERROR_LOGIN"}},
    )
    context = _context(mocker)

    state = await _pick_day(bot, mocker, context)

    assert state == ConversationHandler.END
    assert "credentials" in _sent_texts(context)[-1].lower()
    assert json_repo.get_user(USER_ID).booking_goals == []


@pytest.mark.asyncio
async def test_a_non_json_error_page_ends_the_conversation(wiring, http_mock, mocker):
    """A 502 answers with HTML, and the class listing does not guard .json().

    Left uncaught the conversation would stay parked in SELECTING_CLASS and read
    the member's next message as a class choice.
    """
    from telegram.ext import ConversationHandler

    bot, json_repo, _ = wiring
    _mock_login_success(http_mock)
    http_mock.add(
        rsps_lib.GET,
        classes_endpoint(BOX_NAME),
        body="<html>502 Bad Gateway</html>",
        status=502,
        content_type="text/html",
    )
    context = _context(mocker)

    state = await _pick_day(bot, mocker, context)

    assert state == ConversationHandler.END
    assert "couldn't reach the gym" in _sent_texts(context)[-1].lower()
    assert json_repo.get_user(USER_ID).booking_goals == []


# ── Repeats and expiry ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_scheduling_the_same_class_twice_is_told_not_failed(
    wiring, http_mock, mocker
):
    bot, json_repo, apscheduler = wiring
    apscheduler.start()
    try:
        for _ in range(2):
            _mock_login_success(http_mock)
            _mock_timetable(http_mock, [_booking("2", "1830_60", "WOD")])

        first = _context(mocker)
        await _pick_day(bot, mocker, first)
        await _tap_class(bot, mocker, first, 0)

        second = _context(mocker)
        await _pick_day(bot, mocker, second)
        await _tap_class(bot, mocker, second, 0)

        # Read before shutdown — it empties the jobstore.
        jobs = apscheduler._scheduler.get_jobs()
    finally:
        apscheduler._scheduler.shutdown(wait=False)

    assert len(json_repo.get_user(USER_ID).booking_goals) == 1
    assert len(jobs) == 1
    assert "already had" in _sent_texts(second)[-1].lower()


@pytest.mark.asyncio
async def test_a_callback_with_no_remaining_list_says_it_expired(wiring, mocker):
    """user_data is in-memory, so a restart between the two taps empties it."""
    from telegram.ext import ConversationHandler

    bot, json_repo, _ = wiring
    context = _context(mocker)  # nothing stashed — as after a restart

    state, _ = await _tap_class(bot, mocker, context, 0)

    assert state == ConversationHandler.END
    assert "expired" in _sent_texts(context)[-1].lower()
    assert json_repo.get_user(USER_ID).booking_goals == []
