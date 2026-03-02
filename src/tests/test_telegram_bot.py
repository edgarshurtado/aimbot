"""
Tests for TelegramBot thin UI handlers.

The TelegramBot:
- Constructor: TelegramBot(user_repo: IUserRepository)
- set_use_cases(schedule_uc, remove_uc) for deferred injection
- run() starts polling
- send_message(chat_id, message) for callback use

Each handler tests verifies delegation to use cases — no business logic inline.
"""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock

from domain.models import BookingGoal, User
from domain.ports.user_repository import IUserRepository
from application.use_cases.schedule_booking import ScheduleBookingUseCase
from application.use_cases.remove_booking import RemoveBookingUseCase
from infrastructure.telegram.bot import TelegramBot


@pytest.fixture
def telegram_bot(mocker):
    user_repo = mocker.Mock(spec=IUserRepository)
    schedule_uc = mocker.Mock(spec=ScheduleBookingUseCase)
    remove_uc = mocker.Mock(spec=RemoveBookingUseCase)

    # Patch ApplicationBuilder so TelegramBot doesn't try to connect to Telegram
    mock_app = mocker.Mock()
    mock_app.add_handler = mocker.Mock()
    mock_builder = mocker.Mock()
    mock_builder.token.return_value = mock_builder
    mock_builder.build.return_value = mock_app
    mocker.patch("infrastructure.telegram.bot.ApplicationBuilder", return_value=mock_builder)
    mocker.patch("infrastructure.telegram.bot.get_telegram_token", return_value="test-token")

    bot = TelegramBot(user_repo=user_repo)
    bot.set_use_cases(schedule_uc, remove_uc)
    return bot, user_repo, schedule_uc, remove_uc


def _make_update(user_id, mocker, text=None, args=None):
    update = mocker.Mock()
    update.effective_user.id = user_id
    update.effective_chat.id = user_id
    update.message = mocker.Mock()
    update.message.text = text
    return update


def _make_context(mocker, args=None, user_data=None):
    context = mocker.Mock()
    context.bot = AsyncMock()
    context.args = args or []
    context.user_data = user_data or {}
    return context


# ── /start handler ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_start_handler_authorized_user(telegram_bot, mocker):
    bot, user_repo, schedule_uc, remove_uc = telegram_bot

    user_repo.get_user.return_value = User(id=12345, email="a@b.com", password="pw")
    update = _make_update(12345, mocker)
    context = _make_context(mocker)

    await bot._TelegramBot__start_handler(update, context)

    context.bot.send_message.assert_called_once()
    call_kwargs = context.bot.send_message.call_args.kwargs
    assert "Welcome" in call_kwargs.get("text", "")


@pytest.mark.asyncio
async def test_start_handler_unauthorized_user(telegram_bot, mocker):
    bot, user_repo, schedule_uc, remove_uc = telegram_bot

    user_repo.get_user.return_value = None
    update = _make_update(99999, mocker)
    context = _make_context(mocker)

    await bot._TelegramBot__start_handler(update, context)

    context.bot.send_message.assert_called_once()
    text = context.bot.send_message.call_args.kwargs.get("text", "")
    assert "power" in text.lower() or "permission" in text.lower()


# ── /schedule handler ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_schedule_handler_lists_bookings(telegram_bot, mocker):
    bot, user_repo, schedule_uc, remove_uc = telegram_bot

    user_repo.get_user.return_value = User(
        id=12345,
        email="a@b.com",
        password="pw",
        booking_goals=[
            BookingGoal(booking_date=datetime(2027, 1, 18, 18, 30), name="WOD", job_id="j1")
        ],
    )
    update = _make_update(12345, mocker)
    context = _make_context(mocker)

    await bot._TelegramBot__schedule_handler(update, context)

    context.bot.send_message.assert_called_once()
    text = context.bot.send_message.call_args.kwargs.get("text", "")
    assert "WOD" in text


@pytest.mark.asyncio
async def test_schedule_handler_empty_bookings(telegram_bot, mocker):
    bot, user_repo, schedule_uc, remove_uc = telegram_bot

    user_repo.get_user.return_value = User(
        id=12345, email="a@b.com", password="pw", booking_goals=[]
    )
    update = _make_update(12345, mocker)
    context = _make_context(mocker)

    await bot._TelegramBot__schedule_handler(update, context)

    text = context.bot.send_message.call_args.kwargs.get("text", "")
    assert "don't have any class booking" in text.lower() or "no " in text.lower() or "yet" in text.lower()


# ── /add conversation flow ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_add_flow_unauthorized_user(telegram_bot, mocker):
    bot, user_repo, schedule_uc, remove_uc = telegram_bot

    user_repo.get_user.return_value = None
    update = _make_update(99999, mocker)
    context = _make_context(mocker)

    await bot._TelegramBot__start_booking_handler(update, context)

    schedule_uc.execute.assert_not_called()


@pytest.mark.asyncio
async def test_add_flow_invalid_time_retries(telegram_bot, mocker):
    bot, user_repo, schedule_uc, remove_uc = telegram_bot

    update = _make_update(12345, mocker, text="25:99")
    context = _make_context(mocker, user_data={"selected_date": datetime(2027, 3, 15)})

    await bot._TelegramBot__time_selected_handler(update, context)

    context.bot.send_message.assert_called_once()
    text = context.bot.send_message.call_args.kwargs.get("text", "")
    assert "invalid" in text.lower() or "format" in text.lower()


@pytest.mark.asyncio
async def test_cancel_clears_context(telegram_bot, mocker):
    bot, user_repo, schedule_uc, remove_uc = telegram_bot

    update = _make_update(12345, mocker)
    context = _make_context(mocker, user_data={"selected_date": datetime(2027, 3, 15)})

    await bot._TelegramBot__cancel_booking_handler(update, context)

    context.bot.send_message.assert_called_once()
    text = context.bot.send_message.call_args.kwargs.get("text", "")
    assert "cancel" in text.lower()


# ── /remove handler ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_remove_handler_calls_remove_use_case(telegram_bot, mocker):
    bot, user_repo, schedule_uc, remove_uc = telegram_bot

    user_repo.get_user.return_value = User(
        id=12345,
        email="a@b.com",
        password="pw",
        booking_goals=[
            BookingGoal(booking_date=datetime(2027, 1, 18, 18, 30), name="WOD", job_id="job-to-remove")
        ],
    )
    update = _make_update(12345, mocker)
    context = _make_context(mocker, args=["1"])

    await bot._TelegramBot__remove_booking_handler(update, context)

    remove_uc.execute.assert_called_once_with(12345, "job-to-remove")


# ── Domain objects (not raw dicts) ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_bot_uses_domain_objects_not_dicts(telegram_bot, mocker):
    """Schedule handler reads user.booking_goals (BookingGoal objects), not dicts."""
    bot, user_repo, schedule_uc, remove_uc = telegram_bot

    goals = [BookingGoal(booking_date=datetime(2027, 1, 18, 18, 30), name="WOD", job_id="j1")]
    user = User(id=12345, email="a@b.com", password="pw", booking_goals=goals)
    user_repo.get_user.return_value = user

    update = _make_update(12345, mocker)
    context = _make_context(mocker)

    await bot._TelegramBot__schedule_handler(update, context)

    # Verify get_user was called (domain object retrieval)
    user_repo.get_user.assert_called_once_with(12345)
    # Verify the response included booking goal info from domain object
    text = context.bot.send_message.call_args.kwargs.get("text", "")
    assert "WOD" in text
