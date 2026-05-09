import asyncio
import logging
from datetime import datetime, timedelta

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from application.use_cases.remove_booking import RemoveBookingUseCase
from application.use_cases.schedule_booking import ScheduleBookingUseCase
from domain.ports.user_repository import IUserRepository
from infrastructure.telegram.group_notifier import get_telegram_token

SELECTING_DAY, SELECTING_TIME, SELECTING_CLASS_NAME = range(3)

_VALID_CLASSES = ["WOD", "GYMNASTIC", "OPEN", "HALTEROFILIA"]


class TelegramBot:
    def __init__(self, user_repo: IUserRepository) -> None:
        logging.basicConfig(
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            level=logging.INFO,
        )
        self._user_repo = user_repo
        self._schedule_uc: ScheduleBookingUseCase | None = None
        self._remove_uc: RemoveBookingUseCase | None = None
        self.__application = ApplicationBuilder().token(get_telegram_token()).build()
        self.__register_handlers()

    def set_use_cases(
        self,
        schedule_uc: ScheduleBookingUseCase,
        remove_uc: RemoveBookingUseCase,
    ) -> None:
        self._schedule_uc = schedule_uc
        self._remove_uc = remove_uc

    def run(self) -> None:
        self.__application.run_polling()

    def send_message(self, chat_id: int, message: str) -> None:
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        loop.run_until_complete(
            self.__application.bot.send_message(chat_id=chat_id, text=message)
        )

    def __register_handlers(self) -> None:
        self.__application.add_handler(CommandHandler("start", self.__start_handler))
        self.__application.add_handler(CommandHandler("schedule", self.__schedule_handler))

        booking_conv = ConversationHandler(
            entry_points=[CommandHandler("add", self.__start_booking_handler)],
            states={
                SELECTING_DAY: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.__day_selected_handler)
                ],
                SELECTING_TIME: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.__time_selected_handler)
                ],
                SELECTING_CLASS_NAME: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND, self.__class_name_selected_handler
                    )
                ],
            },
            fallbacks=[CommandHandler("cancel", self.__cancel_booking_handler)],
        )
        self.__application.add_handler(booking_conv)
        self.__application.add_handler(CommandHandler("remove", self.__remove_booking_handler))

    async def __start_handler(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        user = self._user_repo.get_user(update.effective_user.id)
        if user is None:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=(
                    "You don't have power here! "
                    "Ask the master for permission\n\nYour id is: "
                    + str(update.effective_user.id)
                ),
            )
            return
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=(
                "Welcome to Monkey Aim Bot!\n\n"
                "This is a pre-alpha version, so don't be too harsh on me if I fail 🙈\n\n"
                "To start booking classes use the command '/add'\n\n"
                "Don't forget, this will be our little secret 🤫"
            ),
        )

    async def __schedule_handler(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        user = self._user_repo.get_user(update.effective_user.id)
        if user is None or not user.booking_goals:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="You don't have any class booking scheduled yet",
            )
            return
        response = ""
        for idx, goal in enumerate(user.booking_goals):
            response += (
                f"{idx + 1}. {goal.class_start.strftime('%d-%m-%Y %H:%M')} {goal.class_name}\n"
            )
        await context.bot.send_message(chat_id=update.effective_chat.id, text=response)

    def __generate_days_keyboard(self) -> ReplyKeyboardMarkup:
        keyboard = []
        today = datetime.now() + timedelta(days=3)
        for i in range(7):
            day = today + timedelta(days=i)
            button_text = f"{day.strftime('%d-%m')} ({day.strftime('%A')})"
            keyboard.append([button_text])
        return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)

    def __generate_class_keyboard(self) -> ReplyKeyboardMarkup:
        return ReplyKeyboardMarkup(
            [[name] for name in _VALID_CLASSES],
            one_time_keyboard=True,
            resize_keyboard=True,
        )

    async def __start_booking_handler(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        user = self._user_repo.get_user(update.effective_user.id)
        if user is None:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="You don't have power here! Ask the master for permission",
            )
            return ConversationHandler.END
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Select the day for the booking:",
            reply_markup=self.__generate_days_keyboard(),
        )
        return SELECTING_DAY

    async def __day_selected_handler(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        try:
            day_str = update.message.text.split(" ")[0]
            now = datetime.now()
            selected = datetime.strptime(f"{day_str}-{now.year}", "%d-%m-%Y")
            if selected < now.replace(hour=0, minute=0, second=0, microsecond=0):
                selected = datetime.strptime(f"{day_str}-{now.year + 1}", "%d-%m-%Y")
            context.user_data["selected_date"] = selected
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=(
                    f"Selected day: {selected.strftime('%d/%m/%Y')}\n\n"
                    "Please, enter the time in HH:MM format (example: 18:30):"
                ),
                reply_markup=ReplyKeyboardRemove(),
            )
            return SELECTING_TIME
        except (ValueError, IndexError):
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Invalid day format. Please select a day from the keyboard.",
            )
            return SELECTING_DAY

    async def __time_selected_handler(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        time_text = update.message.text
        try:
            hour, minute = map(int, time_text.split(":"))
            if not (0 <= hour < 24 and 0 <= minute < 60):
                raise ValueError("Invalid time")
            context.user_data["selected_time"] = time_text
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"Selected time: {time_text}\n\nPlease, select the class name:",
                reply_markup=self.__generate_class_keyboard(),
            )
            return SELECTING_CLASS_NAME
        except (ValueError, IndexError):
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Invalid time format. Please enter the time in HH:MM format (example: 18:30):",
            )
            return SELECTING_TIME

    async def __class_name_selected_handler(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        class_name = update.message.text.upper()
        if class_name not in _VALID_CLASSES:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Invalid class name. Please select a class name from the keyboard:",
                reply_markup=self.__generate_class_keyboard(),
            )
            return SELECTING_CLASS_NAME

        selected_date = context.user_data.get("selected_date")
        selected_time = context.user_data.get("selected_time")
        if not selected_date or not selected_time:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Error: incomplete booking information. Please start again with /add",
            )
            return ConversationHandler.END

        hour, minute = map(int, selected_time.split(":"))
        class_start = selected_date.replace(hour=hour, minute=minute)

        self._schedule_uc.execute(
            user_id=update.effective_user.id,
            class_start=class_start,
            class_name=class_name,
        )

        user = self._user_repo.get_user(update.effective_user.id)
        email = user.email if user else str(update.effective_user.id)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=(
                f"✅ Booking scheduled for {email}\n"
                f"📅 {class_start.strftime('%d/%m/%Y %H:%M')}\n"
                f"🏋️ {class_name}"
            ),
            reply_markup=ReplyKeyboardRemove(),
        )
        context.user_data.clear()
        return ConversationHandler.END

    @staticmethod
    async def __cancel_booking_handler(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        context.user_data.clear()
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Booking cancelled.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return ConversationHandler.END

    async def __remove_booking_handler(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        [idx_str] = context.args
        idx = int(idx_str) - 1

        user = self._user_repo.get_user(update.effective_user.id)
        selected_goal = user.booking_goals[idx]
        self._remove_uc.execute(update.effective_user.id, selected_goal)

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Scheduled booking removed",
        )
