import json
import logging
from datetime import datetime

import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler

from booking_scheduler import BookingScheduler
from repository import JsonRepository


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
    def __init__(self, booking_scheduler: BookingScheduler, repository: JsonRepository):
        logging.basicConfig(
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            level=logging.INFO
        )
        self.__token = "7837134549:AAFIHT8FjRQKiJ2Yb0ZrHcP8dFtgJce-fjw"
        self.__application = ApplicationBuilder().token(self.__token).build()
        self.__register_handlers()
        self.__scheduler = booking_scheduler
        self.__repository = repository

    def run(self):
        self.__application.run_polling()

    async def send_message(self, message: str):
        await self.__application.bot.send_message(chat_id=-1002328222855, text=message)

    def __register_handlers(self):
        self.__application.add_handler(CommandHandler('start', self.__start_handler))
        self.__application.add_handler(CommandHandler('schedule', self.__schedule_handler))
        self.__application.add_handler(CommandHandler('add', self.__book_class_handler))
        self.__application.add_handler(CommandHandler('remove', self.__remove_booking_handler))

    async def __start_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        if self.__repository.get_user_schedule_configuration(update.effective_user.id) is None:
            await context.bot.send_message(
                chat_id=context.effective_chat.id,
                text="You don't have power here!"
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
           response_text += f'{idx + 1}. {bookingSchedule["datetime"]} {bookingSchedule["name"]}'

        response_text = response_text if response_text != '' else "You don't have any class scheduled yet"
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                       text=response_text)

    async def __book_class_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        [day_and_month, hour, class_name] = context.args
        class_name = class_name.upper()

        now = datetime.now()
        full_date = day_and_month + f'-{now.year}'
        booking_date = datetime.strptime(f'{full_date} {hour}', '%d-%m-%Y %H:%M')

        self.__scheduler.schedule_unique_execution(
            date=booking_date,
            class_name=class_name,
            user_id=update.effective_user.id,
            cb=lambda text: context.bot.send_message(chat_id=update.effective_chat.id, text=text)
        )

        user = self.__repository.get_user_schedule_configuration(update.effective_user.id)['user']['email']
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f'class booking scheduled for {user}\n'
                 f'{booking_date.strftime("%d/%m %H:%M")}'
        )

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



