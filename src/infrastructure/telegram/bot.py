import asyncio
import logging
from datetime import datetime, timedelta

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
)
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    ContextTypes,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from application.use_cases.list_day_classes import ListDayClassesUseCase
from application.use_cases.remove_booking import RemoveBookingUseCase
from application.use_cases.schedule_booking import ScheduleBookingUseCase
from domain.exceptions import AuthenticationFailed
from domain.models import BookingGoal, GymClass
from domain.ports.user_repository import IUserRepository
from infrastructure.telegram.group_notifier import get_telegram_token

logger = logging.getLogger(__name__)

SELECTING_DAY, SELECTING_CLASS = range(2)

# Where the day's Timetable is parked between the two steps of /add. It lives in
# python-telegram-bot's in-memory user_data — no persistence is configured, so a
# restart between the taps empties it.
_DAY_CLASSES = "day_classes"


class TelegramBot:
    def __init__(self, user_repo: IUserRepository) -> None:
        logging.basicConfig(
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            level=logging.INFO,
        )
        self._user_repo = user_repo
        self._schedule_uc: ScheduleBookingUseCase | None = None
        self._remove_uc: RemoveBookingUseCase | None = None
        self._list_day_classes_uc: ListDayClassesUseCase | None = None
        self.__application = ApplicationBuilder().token(get_telegram_token()).build()
        self.__register_handlers()

    def set_use_cases(
        self,
        schedule_uc: ScheduleBookingUseCase,
        remove_uc: RemoveBookingUseCase,
        list_day_classes_uc: ListDayClassesUseCase,
    ) -> None:
        self._schedule_uc = schedule_uc
        self._remove_uc = remove_uc
        self._list_day_classes_uc = list_day_classes_uc

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
                SELECTING_CLASS: [CallbackQueryHandler(self.__class_selected_handler)],
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

    @staticmethod
    def __generate_classes_keyboard(classes: list[GymClass]) -> InlineKeyboardMarkup:
        """One button per real class, identified by its position in the list.

        The label carries the start time as well as the name because either alone
        can repeat within a day; it deliberately shows no spot count, which would
        be stale by Trigger Time. The identity travels as callback data rather
        than as text the member could mistype.
        """
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        f"{gym_class.class_start.strftime('%H:%M')} {gym_class.name}",
                        callback_data=str(idx),
                    )
                ]
                for idx, gym_class in enumerate(classes)
            ]
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
        except (ValueError, IndexError):
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Invalid day format. Please select a day from the keyboard.",
            )
            return SELECTING_DAY

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"Checking the timetable for {selected.strftime('%d/%m/%Y')}…",
            reply_markup=ReplyKeyboardRemove(),
        )

        classes = await self.__fetch_day_classes(update, context, selected)
        if classes is None:
            return ConversationHandler.END

        if not classes:
            context.user_data.clear()
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"No classes published for {selected.strftime('%d/%m/%Y')}.",
            )
            return ConversationHandler.END

        context.user_data[_DAY_CLASSES] = classes
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Select the class:",
            reply_markup=self.__generate_classes_keyboard(classes),
        )
        return SELECTING_CLASS

    async def __fetch_day_classes(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        day: datetime,
    ) -> list[GymClass] | None:
        """The day's Timetable, or None once the member has been told why not.

        Runs off the event loop: the use case logs in and then lists, two blocking
        round trips that would otherwise freeze every other member's conversation.
        """
        try:
            return await asyncio.to_thread(
                self._list_day_classes_uc.execute, update.effective_user.id, day
            )
        except AuthenticationFailed:
            message = "Couldn't sign in to the gym — check the stored credentials."
        except Exception:
            # Deliberately broad: the class listing has no guard around .json(), so
            # an HTML error page from a 502 surfaces as a bare ValueError. Letting
            # it escape would park the conversation in SELECTING_CLASS and feed the
            # member's next message to the class handler.
            logger.exception("Could not read the timetable for %s", day.date())
            message = "Couldn't reach the gym, try again shortly."

        context.user_data.clear()
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text=message
        )
        return None

    async def __class_selected_handler(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        query = update.callback_query
        await query.answer()
        # Drop the buttons so the same class can't be tapped twice.
        await query.edit_message_reply_markup(reply_markup=None)

        classes = context.user_data.get(_DAY_CLASSES) or []
        try:
            gym_class = classes[int(query.data)]
        except (ValueError, IndexError):
            context.user_data.clear()
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="That class list expired. Please start again with /add",
            )
            return ConversationHandler.END

        user_id = update.effective_user.id
        booking_goal = BookingGoal(
            class_start=gym_class.class_start, class_name=gym_class.name
        )

        user = self._user_repo.get_user(user_id)
        already_scheduled = user is not None and booking_goal in user.booking_goals

        self._schedule_uc.execute(user_id=user_id, booking_goal=booking_goal)

        who = user.email if user else str(user_id)
        when = booking_goal.class_start.strftime("%d/%m/%Y %H:%M")
        if already_scheduled:
            text = f"👍 You already had {booking_goal.class_name} on {when} scheduled"
        else:
            text = (
                f"✅ Booking scheduled for {who}\n"
                f"📅 {when}\n"
                f"🏋️ {booking_goal.class_name}"
            )
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text)

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
