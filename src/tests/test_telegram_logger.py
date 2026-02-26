import asyncio
import os
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch

import pytest
from freezegun import freeze_time
from telegram import ReplyKeyboardRemove
from telegram.ext import ConversationHandler

from telegram_logger import (
    TelegramBot,
    TelegramLogger,
    get_telegram_token,
    SELECTING_DAY,
    SELECTING_TIME,
    SELECTING_CLASS_NAME,
)


def make_update(user_id, chat_id, message_text=""):
    update = MagicMock()
    update.effective_user.id = user_id
    update.effective_chat.id = chat_id
    update.message.text = message_text
    return update


def make_context(user_data=None, args=None):
    context = MagicMock()
    context.user_data = user_data if user_data is not None else {}
    context.args = args if args is not None else []
    context.bot = AsyncMock()
    return context


@pytest.fixture
def bot_fixture():
    mock_scheduler = MagicMock()
    mock_repo = MagicMock()
    mock_app = MagicMock()
    mock_app.bot = AsyncMock()
    with patch("telegram_logger.get_telegram_token", return_value="test_token"), \
         patch("telegram_logger.ApplicationBuilder") as mock_builder:
        mock_builder.return_value.token.return_value.build.return_value = mock_app
        bot = TelegramBot(mock_scheduler, mock_repo)
    return bot, mock_app, mock_scheduler, mock_repo


class TestGetTelegramToken:
    def test_returns_prod_token_when_mode_is_prod(self):
        with patch.dict(os.environ, {"MODE": "prod", "TELEGRAM_BOT_TOKEN_PROD": "prod_token"}, clear=True):
            assert get_telegram_token() == "prod_token"

    def test_returns_dev_token_when_mode_is_dev(self):
        with patch.dict(os.environ, {"MODE": "dev", "TELEGRAM_BOT_TOKEN_DEV": "dev_token"}, clear=True):
            assert get_telegram_token() == "dev_token"

    def test_returns_dev_token_when_mode_is_missing(self):
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN_DEV": "dev_token"}, clear=True):
            assert get_telegram_token() == "dev_token"

    def test_raises_error_when_dev_token_is_missing(self):
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError):
                get_telegram_token()


class TestTelegramLogger:
    @pytest.fixture(autouse=True)
    def patch_get_telegram_token(self):
        with patch("telegram_logger.get_telegram_token", return_value="my_token"):
            yield

    def test_send_message_posts_to_correct_url(self):
        with patch("telegram_logger.requests.post") as mock_post:
            logger = TelegramLogger()
            logger.send_message("hello")

            mock_post.assert_called_once()
            url = mock_post.call_args.args[0]
            params = mock_post.call_args.kwargs.get("params", {})
            assert "my_token" in url
            assert params.get("text") == "hello"

    def test_send_message_passes_group_id(self):
        with patch("telegram_logger.requests.post") as mock_post:
            logger = TelegramLogger()
            logger.send_message("hello")

            params = mock_post.call_args.kwargs.get("params", {})
            assert params.get("chat_id") == logger.group_id

    def test_bot_api_url_contains_token(self):
        logger = TelegramLogger()
        assert "my_token" in logger.bot_api_url


class TestTelegramBotInit:
    def test_init_does_not_start_polling(self, bot_fixture):
        _, mock_app, _, _ = bot_fixture
        mock_app.run_polling.assert_not_called()

    def test_send_message_delegates_to_application_bot(self, bot_fixture):
        bot, mock_app, _, _ = bot_fixture
        bot.send_message(chat_id=42, message="x")
        mock_app.bot.send_message.assert_called_once_with(chat_id=42, text="x")


class TestStartHandler:
    def test_start_handler_unauthorized_user_sends_permission_message(self, bot_fixture):
        bot, _, _, mock_repo = bot_fixture
        mock_repo.get_user_schedule_configuration.return_value = None
        update = make_update(user_id=999, chat_id=100)
        context = make_context()

        asyncio.run(bot._TelegramBot__start_handler(update, context))

        context.bot.send_message.assert_called_once()
        text = context.bot.send_message.call_args.kwargs.get("text", "")
        assert "permission" in text
        assert "999" in text

    def test_start_handler_authorized_user_sends_welcome_message(self, bot_fixture):
        bot, _, _, mock_repo = bot_fixture
        mock_repo.get_user_schedule_configuration.return_value = {"user": {"email": "foo@bar.com"}}
        update = make_update(user_id=1, chat_id=100)
        context = make_context()

        asyncio.run(bot._TelegramBot__start_handler(update, context))

        text = context.bot.send_message.call_args.kwargs.get("text", "")
        assert "Welcome" in text
        assert "/add" in text


class TestScheduleHandler:
    def test_schedule_handler_with_no_goals_sends_empty_message(self, bot_fixture):
        bot, _, _, mock_repo = bot_fixture
        mock_repo.get_user_schedule_configuration.return_value = {"bookingGoals": []}
        update = make_update(user_id=1, chat_id=100)
        context = make_context()

        asyncio.run(bot._TelegramBot__schedule_handler(update, context))

        text = context.bot.send_message.call_args.kwargs.get("text", "")
        assert "yet" in text

    def test_schedule_handler_with_goals_lists_them(self, bot_fixture):
        bot, _, _, mock_repo = bot_fixture
        mock_repo.get_user_schedule_configuration.return_value = {
            "bookingGoals": [
                {"datetime": "25-02-2026 18:30", "name": "WOD", "job_id": "abc"},
                {"datetime": "26-02-2026 10:00", "name": "GYMNASTIC", "job_id": "def"},
            ]
        }
        update = make_update(user_id=1, chat_id=100)
        context = make_context()

        asyncio.run(bot._TelegramBot__schedule_handler(update, context))

        text = context.bot.send_message.call_args.kwargs.get("text", "")
        assert "1." in text
        assert "WOD" in text
        assert "2." in text
        assert "GYMNASTIC" in text


class TestStartBookingHandler:
    def test_start_booking_handler_unauthorized_returns_end(self, bot_fixture):
        bot, _, _, mock_repo = bot_fixture
        mock_repo.get_user_schedule_configuration.return_value = None
        update = make_update(user_id=999, chat_id=100)
        context = make_context()

        result = asyncio.run(bot._TelegramBot__start_booking_handler(update, context))

        assert result == ConversationHandler.END

    def test_start_booking_handler_authorized_returns_selecting_day(self, bot_fixture):
        bot, _, _, mock_repo = bot_fixture
        mock_repo.get_user_schedule_configuration.return_value = {"user": {"email": "foo@bar.com"}}
        update = make_update(user_id=1, chat_id=100)
        context = make_context()

        result = asyncio.run(bot._TelegramBot__start_booking_handler(update, context))

        assert result == SELECTING_DAY
        assert context.bot.send_message.call_args.kwargs.get("reply_markup") is not None


class TestDaySelectedHandler:
    @freeze_time("2026-02-20")
    def test_day_selected_valid_format_returns_selecting_time(self, bot_fixture):
        bot, _, _, _ = bot_fixture
        update = make_update(user_id=1, chat_id=100, message_text="25-02 (Wednesday)")
        context = make_context()

        result = asyncio.run(bot._TelegramBot__day_selected_handler(update, context))

        assert result == SELECTING_TIME
        assert context.user_data["selected_date"] == datetime(2026, 2, 25)

    @freeze_time("2026-12-30")
    def test_day_selected_year_rollover(self, bot_fixture):
        bot, _, _, _ = bot_fixture
        update = make_update(user_id=1, chat_id=100, message_text="05-01 (Thursday)")
        context = make_context()

        result = asyncio.run(bot._TelegramBot__day_selected_handler(update, context))

        assert result == SELECTING_TIME
        assert context.user_data["selected_date"].year == 2027

    @freeze_time("2026-02-20")
    def test_day_selected_today_no_rollover(self, bot_fixture):
        bot, _, _, _ = bot_fixture
        update = make_update(user_id=1, chat_id=100, message_text="20-02 (Friday)")
        context = make_context()

        result = asyncio.run(bot._TelegramBot__day_selected_handler(update, context))

        assert result == SELECTING_TIME
        assert context.user_data["selected_date"].year == 2026

    def test_day_selected_invalid_format_returns_selecting_day(self, bot_fixture):
        bot, _, _, _ = bot_fixture
        update = make_update(user_id=1, chat_id=100, message_text="not-a-date")
        context = make_context()

        result = asyncio.run(bot._TelegramBot__day_selected_handler(update, context))

        assert result == SELECTING_DAY
        assert "selected_date" not in context.user_data

    def test_day_selected_empty_string_returns_selecting_day(self, bot_fixture):
        bot, _, _, _ = bot_fixture
        update = make_update(user_id=1, chat_id=100, message_text="")
        context = make_context()

        result = asyncio.run(bot._TelegramBot__day_selected_handler(update, context))

        assert result == SELECTING_DAY


class TestTimeSelectedHandler:
    def test_time_selected_valid_time_returns_selecting_class_name(self, bot_fixture):
        bot, _, _, _ = bot_fixture
        update = make_update(user_id=1, chat_id=100, message_text="18:30")
        context = make_context()

        result = asyncio.run(bot._TelegramBot__time_selected_handler(update, context))

        assert result == SELECTING_CLASS_NAME
        assert context.bot.send_message.call_args.kwargs.get("reply_markup") is not None

    def test_time_selected_midnight_is_valid(self, bot_fixture):
        bot, _, _, _ = bot_fixture
        update = make_update(user_id=1, chat_id=100, message_text="00:00")
        context = make_context()

        result = asyncio.run(bot._TelegramBot__time_selected_handler(update, context))

        assert result == SELECTING_CLASS_NAME

    def test_time_selected_last_valid_minute_is_valid(self, bot_fixture):
        bot, _, _, _ = bot_fixture
        update = make_update(user_id=1, chat_id=100, message_text="23:59")
        context = make_context()

        result = asyncio.run(bot._TelegramBot__time_selected_handler(update, context))

        assert result == SELECTING_CLASS_NAME

    def test_time_selected_invalid_hour_returns_selecting_time(self, bot_fixture):
        bot, _, _, _ = bot_fixture
        update = make_update(user_id=1, chat_id=100, message_text="24:00")
        context = make_context()

        result = asyncio.run(bot._TelegramBot__time_selected_handler(update, context))

        assert result == SELECTING_TIME
        assert "selected_time" not in context.user_data

    def test_time_selected_invalid_minute_returns_selecting_time(self, bot_fixture):
        bot, _, _, _ = bot_fixture
        update = make_update(user_id=1, chat_id=100, message_text="25:99")
        context = make_context()

        result = asyncio.run(bot._TelegramBot__time_selected_handler(update, context))

        assert result == SELECTING_TIME

    def test_time_selected_no_colon_returns_selecting_time(self, bot_fixture):
        bot, _, _, _ = bot_fixture
        update = make_update(user_id=1, chat_id=100, message_text="1830")
        context = make_context()

        result = asyncio.run(bot._TelegramBot__time_selected_handler(update, context))

        assert result == SELECTING_TIME

    def test_time_selected_non_numeric_returns_selecting_time(self, bot_fixture):
        bot, _, _, _ = bot_fixture
        update = make_update(user_id=1, chat_id=100, message_text="ab:cd")
        context = make_context()

        result = asyncio.run(bot._TelegramBot__time_selected_handler(update, context))

        assert result == SELECTING_TIME


class TestClassNameSelectedHandler:
    def test_class_name_valid_wod_schedules_and_confirms(self, bot_fixture):
        bot, _, mock_scheduler, mock_repo = bot_fixture
        mock_repo.get_user_schedule_configuration.return_value = {
            "user": {"email": "user@test.com"},
            "bookingGoals": [],
        }
        user_data = {
            "selected_date": datetime(2026, 2, 25),
            "selected_time": "18:30",
        }
        update = make_update(user_id=1, chat_id=100, message_text="WOD")
        context = make_context(user_data=user_data)

        result = asyncio.run(bot._TelegramBot__class_name_selected_handler(update, context))

        assert result == ConversationHandler.END
        mock_scheduler.schedule_unique_execution.assert_called_once()
        call_kwargs = mock_scheduler.schedule_unique_execution.call_args.kwargs
        assert call_kwargs["date"] == datetime(2026, 2, 25, 18, 30)
        assert call_kwargs["class_name"] == "WOD"
        assert call_kwargs["user_id"] == 1
        text = context.bot.send_message.call_args.kwargs.get("text", "")
        assert "user@test.com" in text
        assert not context.user_data

    def test_class_name_lowercase_is_uppercased_and_accepted(self, bot_fixture):
        bot, _, mock_scheduler, mock_repo = bot_fixture
        mock_repo.get_user_schedule_configuration.return_value = {
            "user": {"email": "user@test.com"},
            "bookingGoals": [],
        }
        user_data = {
            "selected_date": datetime(2026, 2, 25),
            "selected_time": "18:30",
        }
        update = make_update(user_id=1, chat_id=100, message_text="wod")
        context = make_context(user_data=user_data)

        asyncio.run(bot._TelegramBot__class_name_selected_handler(update, context))

        call_kwargs = mock_scheduler.schedule_unique_execution.call_args.kwargs
        assert call_kwargs["class_name"] == "WOD"

    @pytest.mark.parametrize("class_name", ["WOD", "GYMNASTIC", "OPEN", "HALTEROFILIA"])
    def test_class_name_all_valid_names_accepted(self, bot_fixture, class_name):
        bot, _, mock_scheduler, mock_repo = bot_fixture
        mock_repo.get_user_schedule_configuration.return_value = {
            "user": {"email": "user@test.com"},
            "bookingGoals": [],
        }
        user_data = {
            "selected_date": datetime(2026, 2, 25),
            "selected_time": "18:30",
        }
        update = make_update(user_id=1, chat_id=100, message_text=class_name)
        context = make_context(user_data=user_data)

        result = asyncio.run(bot._TelegramBot__class_name_selected_handler(update, context))

        assert result == ConversationHandler.END
        mock_scheduler.schedule_unique_execution.assert_called_once()

    def test_class_name_invalid_stays_in_selecting_class_name(self, bot_fixture):
        bot, _, mock_scheduler, _ = bot_fixture
        update = make_update(user_id=1, chat_id=100, message_text="YOGA")
        context = make_context()

        result = asyncio.run(bot._TelegramBot__class_name_selected_handler(update, context))

        assert result == SELECTING_CLASS_NAME
        mock_scheduler.schedule_unique_execution.assert_not_called()
        assert context.bot.send_message.call_args.kwargs.get("reply_markup") is not None

    def test_class_name_selected_missing_date_returns_end(self, bot_fixture):
        bot, _, mock_scheduler, _ = bot_fixture
        update = make_update(user_id=1, chat_id=100, message_text="WOD")
        context = make_context(user_data={})

        result = asyncio.run(bot._TelegramBot__class_name_selected_handler(update, context))

        assert result == ConversationHandler.END
        mock_scheduler.schedule_unique_execution.assert_not_called()
        text = context.bot.send_message.call_args.kwargs.get("text", "")
        assert "/add" in text

    def test_class_name_selected_missing_time_returns_end(self, bot_fixture):
        bot, _, mock_scheduler, _ = bot_fixture
        update = make_update(user_id=1, chat_id=100, message_text="WOD")
        context = make_context(user_data={"selected_date": datetime(2026, 2, 25)})

        result = asyncio.run(bot._TelegramBot__class_name_selected_handler(update, context))

        assert result == ConversationHandler.END
        mock_scheduler.schedule_unique_execution.assert_not_called()

    def test_class_name_selected_callback_calls_send_message(self, bot_fixture):
        bot, mock_app, mock_scheduler, mock_repo = bot_fixture
        mock_repo.get_user_schedule_configuration.return_value = {
            "user": {"email": "user@test.com"},
            "bookingGoals": [],
        }
        user_data = {
            "selected_date": datetime(2026, 2, 25),
            "selected_time": "18:30",
        }
        update = make_update(user_id=1, chat_id=100, message_text="WOD")
        context = make_context(user_data=user_data)

        asyncio.run(bot._TelegramBot__class_name_selected_handler(update, context))

        cb = mock_scheduler.schedule_unique_execution.call_args.kwargs["cb"]
        cb("booking confirmed")

        mock_app.bot.send_message.assert_called_once_with(chat_id=100, text="booking confirmed")


class TestCancelBookingHandler:
    def test_cancel_clears_user_data_and_returns_end(self, bot_fixture):
        bot, _, _, _ = bot_fixture
        user_data = {"selected_date": datetime(2026, 2, 25), "selected_time": "18:30"}
        update = make_update(user_id=1, chat_id=100)
        context = make_context(user_data=user_data)

        result = asyncio.run(bot._TelegramBot__cancel_booking_handler(update, context))

        assert result == ConversationHandler.END
        assert not context.user_data
        reply_markup = context.bot.send_message.call_args.kwargs.get("reply_markup")
        assert isinstance(reply_markup, ReplyKeyboardRemove)

    def test_cancel_with_empty_user_data(self, bot_fixture):
        bot, _, _, _ = bot_fixture
        update = make_update(user_id=1, chat_id=100)
        context = make_context(user_data={})

        result = asyncio.run(bot._TelegramBot__cancel_booking_handler(update, context))

        assert result == ConversationHandler.END


class TestRemoveBookingHandler:
    def test_remove_booking_removes_correct_job(self, bot_fixture):
        bot, _, mock_scheduler, mock_repo = bot_fixture
        mock_repo.get_user_schedule_configuration.return_value = {
            "bookingGoals": [
                {"datetime": "25-02-2026 18:30", "name": "WOD", "job_id": "job-abc-123"},
                {"datetime": "26-02-2026 10:00", "name": "GYMNASTIC", "job_id": "job-def-456"},
            ]
        }
        update = make_update(user_id=1, chat_id=100)
        context = make_context(args=["1"])

        asyncio.run(bot._TelegramBot__remove_booking_handler(update, context))

        mock_scheduler.remove_unique_execution.assert_called_once_with(1, "job-abc-123")

    def test_remove_booking_second_item(self, bot_fixture):
        bot, _, mock_scheduler, mock_repo = bot_fixture
        mock_repo.get_user_schedule_configuration.return_value = {
            "bookingGoals": [
                {"datetime": "25-02-2026 18:30", "name": "WOD", "job_id": "job-abc-123"},
                {"datetime": "26-02-2026 10:00", "name": "GYMNASTIC", "job_id": "job-def-456"},
            ]
        }
        update = make_update(user_id=1, chat_id=100)
        context = make_context(args=["2"])

        asyncio.run(bot._TelegramBot__remove_booking_handler(update, context))

        mock_scheduler.remove_unique_execution.assert_called_once_with(1, "job-def-456")

    def test_remove_booking_sends_confirmation_message(self, bot_fixture):
        bot, _, _, mock_repo = bot_fixture
        mock_repo.get_user_schedule_configuration.return_value = {
            "bookingGoals": [
                {"datetime": "25-02-2026 18:30", "name": "WOD", "job_id": "job-abc-123"},
            ]
        }
        update = make_update(user_id=1, chat_id=100)
        context = make_context(args=["1"])

        asyncio.run(bot._TelegramBot__remove_booking_handler(update, context))

        text = context.bot.send_message.call_args.kwargs.get("text", "")
        assert "removed" in text
