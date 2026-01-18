import asyncio
import logging
import os
from datetime import datetime, timedelta

import requests
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder, 
    ContextTypes, 
    CommandHandler, 
    ConversationHandler,
    MessageHandler,
    filters
)

from booking_scheduler import BookingScheduler
from repository import JsonRepository


def get_telegram_token():
    """Get telegram token based on MODE environment variable.
    If MODE=prod, uses TELEGRAM_BOT_TOKEN_PROD, otherwise uses TELEGRAM_BOT_TOKEN_DEV.
    """
    mode = os.getenv("MODE", "").lower()
    token = None
    if mode == "prod":
        token = os.getenv("TELEGRAM_BOT_TOKEN_PROD")
    else:
        token = os.getenv("TELEGRAM_BOT_TOKEN_DEV")
        if not token:
            raise ValueError("TELEGRAM_BOT_TOKEN_DEV environment variable is not set")
    return token


class TelegramLogger:
    def __init__(self):
        self.group_id = -1002328222855
        self.bot_api_url = f"https://api.telegram.org/bot{get_telegram_token()}/"

    def send_message(self, message: str):
        requests.post(
            self.bot_api_url + "sendMessage",
            params={"chat_id": self.group_id, "text": message})


# States for the booking conversation
SELECTING_DAY, SELECTING_TIME, SELECTING_CLASS_NAME = range(3)


class TelegramBot:
    def __init__(self, booking_scheduler: BookingScheduler, repository: JsonRepository):
        logging.basicConfig(
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            level=logging.INFO
        )
        self.__application = ApplicationBuilder().token(get_telegram_token()).build()
        self.__register_handlers()
        self.__scheduler = booking_scheduler
        self.__repository = repository

    def run(self):
        self.__application.run_polling()

    def send_message(self, chat_id: int, message: str):
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        loop.run_until_complete(self.__application.bot.send_message(chat_id=chat_id, text=message))

    def __register_handlers(self):
        self.__application.add_handler(CommandHandler('start', self.__start_handler))
        self.__application.add_handler(CommandHandler('schedule', self.__schedule_handler))
        
        # ConversationHandler for the booking process
        booking_conv_handler = ConversationHandler(
            entry_points=[CommandHandler('add', self.__start_booking_handler)],
            states={
                SELECTING_DAY: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.__day_selected_handler)],
                SELECTING_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.__time_selected_handler)],
                SELECTING_CLASS_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.__class_name_selected_handler)],
            },
            fallbacks=[CommandHandler('cancel', self.__cancel_booking_handler)],
        )
        self.__application.add_handler(booking_conv_handler)
        
        self.__application.add_handler(CommandHandler('remove', self.__remove_booking_handler))

    async def __start_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        if self.__repository.get_user_schedule_configuration(update.effective_user.id) is None:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="You don't have power here! Ask the master for permission\n\n Your id is:" + str(update.effective_user.id)
            )
            return

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Welcome to Monkey Aim Bot!\n\n"
            "This is a pre-alpha version, so don't be too harsh on me if I fail on something 🙈\n\n"
            "To start booking classes use the command '/add'\n\n"
            "Don't forget, this will be our little secret 🤫"
        )

    async def __schedule_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_schedule_config = self.__repository.get_user_schedule_configuration(update.effective_user.id)
        response_text = ''
        for idx, bookingSchedule in enumerate(user_schedule_config["bookingGoals"]):
           response_text += f'{idx + 1}. {bookingSchedule["datetime"]} {bookingSchedule["name"]}\n'

        response_text = response_text if response_text != '' else "You don't have any class booking scheduled yet"
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                       text=response_text)

    def __generate_days_keyboard(self):
        keyboard = []
        today = datetime.now() + timedelta(days=3)
        
        for i in range(7):
            day = today + timedelta(days=i)
            # Format: "DD-MM (Weekday)"
            day_str = day.strftime("%d-%m")
            weekday = day.strftime("%A")
            button_text = f"{day_str} ({weekday})"
            keyboard.append([button_text])
        
        return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)

    def __generate_class_name_keyboard(self):
        """Generate a keyboard with predefined class names"""
        class_names = ["WOD", "GYMNASTICS", "OPEN", "HALTEROFILIA"]
        keyboard = [[name] for name in class_names]
        return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)

    async def __start_booking_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start the booking process showing the keyboard with the next 5 days"""
        if self.__repository.get_user_schedule_configuration(update.effective_user.id) is None:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="You don't have power here! Ask the master for permission"
            )
            return ConversationHandler.END

        keyboard = self.__generate_days_keyboard()
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Select the day for the booking:",
            reply_markup=keyboard
        )
        return SELECTING_DAY

    async def __day_selected_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle day selection and ask for time"""
        selected_day_text = update.message.text
        
        # Extract date from text (format: "DD-MM (Weekday)")
        try:
            day_str = selected_day_text.split(' ')[0]  # Get "DD-MM"
            now = datetime.now()
            
            # Try with current year first
            full_date = day_str + f'-{now.year}'
            selected_date = datetime.strptime(full_date, '%d-%m-%Y')
            
            # If date is before today, probably it's from next year
            if selected_date < now.replace(hour=0, minute=0, second=0, microsecond=0):
                full_date = day_str + f'-{now.year + 1}'
                selected_date = datetime.strptime(full_date, '%d-%m-%Y')
            
            # Save date in context
            context.user_data['selected_date'] = selected_date
            
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"Selected day: {selected_date.strftime('%d/%m/%Y')}\n\n"
                     "Please, enter the time in HH:MM format (example: 18:30):",
                reply_markup=ReplyKeyboardRemove()
            )
            return SELECTING_TIME
        except (ValueError, IndexError) as e:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Invalid day format. Please select a day from the keyboard."
            )
            return SELECTING_DAY

    async def __time_selected_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle time selection and ask for class name"""
        time_text = update.message.text
        
        # Validate time format
        try:
            hour, minute = map(int, time_text.split(':'))
            if not (0 <= hour < 24 and 0 <= minute < 60):
                raise ValueError("Invalid time")
            
            # Save time in context
            context.user_data['selected_time'] = time_text
            
            keyboard = self.__generate_class_name_keyboard()
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"Selected time: {time_text}\n\n"
                     "Please, select the class name:",
                reply_markup=keyboard
            )
            return SELECTING_CLASS_NAME
        except (ValueError, IndexError) as e:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Invalid time format. Please enter the time in HH:MM format (example: 18:30):"
            )
            return SELECTING_TIME

    async def __class_name_selected_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle class name selection and complete the booking"""
        class_name = update.message.text.upper()
        valid_class_names = ["WOD", "GYMNASTICS", "OPEN", "HALTEROFILIA"]
        
        # Validate class name
        if class_name not in valid_class_names:
            keyboard = self.__generate_class_name_keyboard()
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Invalid class name. Please select a class name from the keyboard:",
                reply_markup=keyboard
            )
            return SELECTING_CLASS_NAME
        
        selected_date = context.user_data.get('selected_date')
        selected_time = context.user_data.get('selected_time')
        
        if not selected_date or not selected_time:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Error: incomplete booking information. Please start again with /add"
            )
            return ConversationHandler.END
        
        # Build full date
        hour, minute = map(int, selected_time.split(':'))
        booking_date = selected_date.replace(hour=hour, minute=minute)
        
        # Schedule the booking
        self.__scheduler.schedule_unique_execution(
            date=booking_date,
            class_name=class_name,
            user_id=update.effective_user.id,
            cb=lambda text: self.send_message(chat_id=update.effective_chat.id, message=text)
        )
        
        user = self.__repository.get_user_schedule_configuration(update.effective_user.id)['user']['email']
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f'✅ Booking scheduled for {user}\n'
                 f'📅 {booking_date.strftime("%d/%m/%Y %H:%M")}\n'
                 f'🏋️ {class_name}',
            reply_markup=ReplyKeyboardRemove()
        )
        
        # Clear context data
        context.user_data.clear()
        return ConversationHandler.END

    async def __cancel_booking_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel the booking process"""
        context.user_data.clear()
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Booking cancelled.",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END

    async def __remove_booking_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        [job_to_delete_idx] = context.args
        job_to_delete_idx = int(job_to_delete_idx) - 1

        user_booking_jobs = self.__repository.get_user_schedule_configuration(update.effective_user.id)['bookingGoals']
        selected_job = user_booking_jobs[job_to_delete_idx]
        self.__scheduler.remove_unique_execution(update.effective_user.id, selected_job['job_id'])

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text='Scheduled booking removed'
        )



