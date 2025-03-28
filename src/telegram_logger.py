import logging
import json
from datetime import datetime, timedelta

import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler
from booking_scheduler import BookingScheduler
from src.box_data import days_in_advance


class TelegramLogger:
    def __init__(self):
        self.token = "7837134549:AAFIHT8FjRQKiJ2Yb0ZrHcP8dFtgJce-fjw"
        self.group_id = -1002328222855
        self.bot_api_url = "https://api.telegram.org/bot7837134549:AAFIHT8FjRQKiJ2Yb0ZrHcP8dFtgJce-fjw/"

    def send_message(self, message: str):
        requests.post(
            self.bot_api_url + "sendMessage",
            params={"chat_id": self.group_id, "text": message})


class TelegramBot:
    def __init__(self, booking_scheduler: BookingScheduler):
        logging.basicConfig(
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            level=logging.INFO
        )
        self.__application = ApplicationBuilder().token("7837134549:AAFIHT8FjRQKiJ2Yb0ZrHcP8dFtgJce-fjw").build()
        self.__register_handlers()
        self.__scheduler = booking_scheduler

    def run(self):
        self.__application.run_polling()

    def __register_handlers(self):
        self.__application.add_handler(CommandHandler('schedule', self.__schedule_handler))
        self.__application.add_handler(CommandHandler('add', self.__book_class))


    async def __schedule_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_schedule_config = self.__scheduler.get_user_schedule_configuration(update.effective_user.id)
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                       text=f'Recurrent bookings:\n'
                                            f'{json.dumps(user_schedule_config['recurrentBookingGoals'], indent=4)}'
                                            f'\n\nSingle bookings:\n'
                                            f'{json.dumps(user_schedule_config['bookingGoals'], indent=4)}'
                                       )

    async def __book_class(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        [day_and_month, hour, class_name] = context.args

        now = datetime.now()
        full_date = day_and_month + f'-{now.year}'
        booking_date = datetime.strptime(f'{full_date} {hour}', '%d-%m-%Y %H:%M')

        self.__scheduler.schedule_unique_execution(
            date=booking_date - timedelta(days=days_in_advance),
            class_name=class_name,
            user_id=update.effective_user.id,
            cb=lambda text: context.bot.send_message(chat_id=update.effective_chat.id, text=text)
        )

        user = self.__scheduler.get_user_schedule_configuration(update.effective_user.id)['user']['email']
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f'class booking scheduled for {user}\n'
                 f'{booking_date.strftime("%d/%m %H:%M")}'
        )
