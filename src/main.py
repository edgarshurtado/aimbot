import asyncio
import os
import json
from datetime import datetime, timedelta, time
from apscheduler.schedulers.background import BackgroundScheduler

from box_data import box_id, box_name, days_in_advance
from constants import days_of_week_index

from client import AimHarderClient
from exceptions import (
    NoBookingGoal,
    BoxClosed,
    MESSAGE_BOX_IS_CLOSED,
)
from booking_scheduler import BookingScheduler
from repository import JsonRepository
from telegram_logger import TelegramBot, TelegramLogger


def get_class_to_book(classes: list[dict], target_time: str, class_name: str):
    if not classes or len(classes) == 0:
        raise BoxClosed(MESSAGE_BOX_IS_CLOSED)

    classes = list(filter(lambda _class: target_time in _class["timeid"], classes))
    _class = list(filter(lambda _class: class_name in _class["className"], classes))
    if len(_class) == 0:
        raise NoBookingGoal(
            f"No class with the text `{class_name}` in its name at time `{target_time}`"
        )
    return _class[0]["id"]


def execution(email, password, target_time, class_name):
    client = AimHarderClient(
        email=email, password=password, box_id=box_id, box_name=box_name
    )
    target_day = datetime.today() + timedelta(days=days_in_advance)
    classes = client.get_classes(target_day)
    class_id = get_class_to_book(classes, target_time, class_name)
    client.book_class(target_day, class_id)

    hour = int(target_time[0:2])
    minute = int(target_time[2:4])
    print(f'class booked for {email}: {class_name} {hour}:{minute}')
    TelegramLogger().send_message(f'💪 class booked for {email}: {class_name} {hour}:{minute}')


def schedule_recurrent_execution(day_of_week_execution, class_data, user):
    hour = int(class_data['time'][0:2])
    minute = int(class_data['time'][2:4])
    class_name = class_data["name"]
    class_time = time(hour, minute)
    print(
        f'register task for class {class_name} on day {day_of_week_str}, {class_time.strftime("%H:%M")}')
    scheduler.add_job(
        execution,
        trigger='cron',
        hour=int(class_data['time'][0:2]),
        minute=int(class_data['time'][2:4]),
        day_of_week=day_of_week_execution,
        kwargs=dict(
            email=user["email"],
            password=user["password"],
            target_time=class_data["time"],
            class_name=class_data["name"],
        )
    )

def load_schedule():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(script_dir, 'schedule.json')

    with open(file_path, 'r') as f:
        return json.load(f)

if __name__ == "__main__":
    scheduler = BackgroundScheduler()
    scheduler.start()

    repository = JsonRepository()
    booking_scheduler = BookingScheduler(repository)
    booking_scheduler.start()
    telegram_bot = TelegramBot(booking_scheduler, repository)

    user_schedules = load_schedule()
    for schedule in user_schedules:
        user = schedule["user"]
        print(f'\nRegister tasks for user {user["email"]}')
        for day_of_week_str, classes_data in schedule["recurrentBookingGoals"].items():
            day_of_week_execution = (days_of_week_index[day_of_week_str] - days_in_advance) % 7
            for class_data in classes_data:
                schedule_recurrent_execution(day_of_week_execution, class_data, user)
        for unique_booking_goal in schedule["bookingGoals"]:
            booking_scheduler.schedule_unique_execution(
                date=datetime.strptime(unique_booking_goal["datetime"], "%d-%m-%Y %H:%M"),
                class_name=unique_booking_goal["name"],
                user_id=user["id"],
                cb=lambda text: asyncio.create_task(telegram_bot.send_message(text))
            )

    telegram_bot.run()
