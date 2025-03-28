import logging
import os
import json
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler


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
    def __init__(self):
        logging.basicConfig(
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            level=logging.INFO
        )
        self.__application = ApplicationBuilder().token("7837134549:AAFIHT8FjRQKiJ2Yb0ZrHcP8dFtgJce-fjw").build()
        self.__register_handlers()

    def run(self):
        self.__application.run_polling()

    def __register_handlers(self):
        self.__register_get_schedule_handler()

    def __register_get_schedule_handler(self):
        self.__application.add_handler(CommandHandler('schedule', self.__schedule_handler))

    @staticmethod
    async def __schedule_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(script_dir, 'schedule.json')
        with open(file_path, 'r') as f:
            schedules = json.load(f)
            user_schedules = next(user_schedule for user_schedule in schedules if user_schedule["user"]["id"] == update.effective_user.id)
            await context.bot.send_message(chat_id=update.effective_chat.id,
                                           text=f'Recurrent bookings:\n'
                                                f'{json.dumps(user_schedules['recurrentBookingGoals'], indent=4)}'
                                                f'\n\nSingle bookings:\n'
                                                f'{json.dumps(user_schedules['bookingGoals'], indent=4)}'
                                           )

