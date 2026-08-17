"""
Integration tests for /schedule listing Booking Goals in the order they will fire.

Real repository, real scheduler, real use cases, real bot handlers. Only Telegram
is faked out; these two commands touch no HTTP at all.

The number /schedule prints and the number /remove consumes must address the same
list. These tests seed the store deliberately out of order so that insertion order
and chronological order disagree — the only way to tell which one the bot is using.
"""

import json
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from domain.ports.gym_config import IGymConfig
from domain.ports.notifier import IUserNotifier
from application.use_cases.list_day_classes import ListDayClassesUseCase
from application.use_cases.remove_booking import RemoveBookingUseCase
from application.use_cases.schedule_booking import ScheduleBookingUseCase
from infrastructure.aimharder.client_factory import AimHarderClientFactory
from infrastructure.aimharder.gym_config import IAimHarderGym
from infrastructure.persistence.json_repository import JsonRepository
from infrastructure.scheduling.apscheduler import APSchedulerAdapter
from infrastructure.telegram.bot import TelegramBot

USER_ID = 66666666

# Seeded in an order no member would produce by accident: the goal stored first is
# the one that fires last. Every assertion below would also pass under insertion
# order if these were seeded chronologically.
LAST_STORED_FIRST = {"datetime": "22-06-2027 07:00", "name": "WOD"}
EARLIEST = {"datetime": "15-06-2027 10:00", "name": "WOD"}
MIDDLE = {"datetime": "18-06-2027 19:00", "name": "Halterofilia"}


@pytest.fixture
def schedule_file(tmp_path):
    data = [
        {
            "user": {
                "email": "some-email@gmail.com",
                "password": "password",
                "id": USER_ID,
            },
            "bookingGoals": [LAST_STORED_FIRST, EARLIEST, MIDDLE],
            "recurrentBookingGoals": {},
        }
    ]
    dst = tmp_path / "test_schedule.json"
    dst.write_text(json.dumps(data, indent=4))
    return str(dst)


@pytest.fixture
def wiring(schedule_file, mocker):
    mock_builder = mocker.Mock()
    mock_builder.token.return_value = mock_builder
    mock_builder.build.return_value = mocker.Mock()
    mocker.patch(
        "infrastructure.telegram.bot.ApplicationBuilder", return_value=mock_builder
    )
    mocker.patch(
        "infrastructure.telegram.bot.get_telegram_token", return_value="test-token"
    )

    gym = mocker.Mock(spec=IAimHarderGym)
    gym.box_id = 9824
    gym.box_name = "themonkeybox"
    gym.days_in_advance = 3

    gym_config = mocker.Mock(spec=IGymConfig)
    gym_config.booking_trigger_time.side_effect = lambda class_start: class_start

    json_repo = JsonRepository(schedule_file)
    factory = AimHarderClientFactory(gym=gym)
    apscheduler = APSchedulerAdapter(on_job_execute=mocker.Mock())

    bot = TelegramBot(user_repo=json_repo)
    bot.set_use_cases(
        ScheduleBookingUseCase(json_repo, json_repo, apscheduler, gym_config),
        RemoveBookingUseCase(json_repo, apscheduler),
        ListDayClassesUseCase(json_repo, factory),
    )
    return SimpleNamespace(
        bot=bot,
        repo=json_repo,
        schedule_file=schedule_file,
        notifier=mocker.Mock(spec=IUserNotifier),
    )


def _update(mocker):
    update = mocker.Mock()
    update.effective_user.id = USER_ID
    update.effective_chat.id = USER_ID
    update.message = mocker.Mock()
    return update


def _context(mocker, args=None):
    context = mocker.Mock()
    context.bot = AsyncMock()
    context.args = args or []
    context.user_data = {}
    return context


def _sent_texts(context):
    return [c.kwargs.get("text", "") for c in context.bot.send_message.call_args_list]


def _goals_on_disk(schedule_file):
    """What a fresh process would read back, not what the live instance remembers."""
    return [
        (goal.class_start, goal.class_name)
        for goal in JsonRepository(schedule_file).get_user(USER_ID).booking_goals
    ]


# ── /schedule ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_schedule_lists_booking_goals_soonest_first(wiring, mocker):
    context = _context(mocker)

    await wiring.bot._TelegramBot__schedule_handler(_update(mocker), context)

    assert _sent_texts(context)[-1] == (
        "1. 15-06-2027 10:00 WOD\n"
        "2. 18-06-2027 19:00 Halterofilia\n"
        "3. 22-06-2027 07:00 WOD\n"
    )


# ── /remove agrees with what /schedule printed ────────────────────────────────


@pytest.mark.asyncio
async def test_remove_1_deletes_the_goal_listed_first(wiring, mocker):
    """Under insertion order this deletes the 22-06 WOD — the member's last class."""
    await wiring.bot._TelegramBot__remove_booking_handler(
        _update(mocker), _context(mocker, args=["1"])
    )

    assert _goals_on_disk(wiring.schedule_file) == [
        (datetime(2027, 6, 18, 19, 0), "Halterofilia"),
        (datetime(2027, 6, 22, 7, 0), "WOD"),
    ]


@pytest.mark.asyncio
async def test_remove_3_deletes_the_goal_listed_last(wiring, mocker):
    """The far end of the list, where an off-by-one would still look plausible."""
    await wiring.bot._TelegramBot__remove_booking_handler(
        _update(mocker), _context(mocker, args=["3"])
    )

    assert _goals_on_disk(wiring.schedule_file) == [
        (datetime(2027, 6, 15, 10, 0), "WOD"),
        (datetime(2027, 6, 18, 19, 0), "Halterofilia"),
    ]


@pytest.mark.asyncio
async def test_remove_names_the_goal_it_deleted(wiring, mocker):
    """A goal firing between /schedule and /remove shifts every number down by one.

    Naming the deletion is what makes that visible instead of silent.
    """
    context = _context(mocker, args=["1"])

    await wiring.bot._TelegramBot__remove_booking_handler(_update(mocker), context)

    assert "15-06-2027 10:00 WOD" in _sent_texts(context)[-1]
