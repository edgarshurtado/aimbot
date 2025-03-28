from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from box_data import box_id, box_name, days_in_advance
import os
import json
from client import AimHarderClient
from exceptions import (
    NoBookingGoal,
    BoxClosed,
    MESSAGE_BOX_IS_CLOSED,
)


class BookingScheduler:
    def __init__(self):
        self.__scheduler = BackgroundScheduler()
        self.__schedules_configuration = self.__load_schedules_configuration()

    def start(self):
        self.__scheduler.start()

    def schedule_unique_execution(self, date: datetime, class_name, user_id, cb):
        self.__scheduler.add_job(
            self.__execution,
            trigger=DateTrigger(run_date=date - timedelta(days=days_in_advance)),
            kwargs=dict(
                user_id=user_id,
                target_time=date.strftime('%H%M'),
                class_name=class_name,
                cb=cb
            )
        )

    def get_user_schedule_configuration(self, user_id):
        return next(data for data in self.__schedules_configuration if data['user']['id'] == user_id)

    def __execution(self, user_id, target_time, class_name, cb):
        user = self.get_user_schedule_configuration(user_id)['user']
        email = user['email']
        password = user['password']

        client = AimHarderClient(
            email=email, password=password, box_id=box_id, box_name=box_name
        )
        target_day = datetime.today() + timedelta(days=days_in_advance)
        classes = client.get_classes(target_day)
        class_id = self.__get_class_to_book(classes, target_time, class_name)
        client.book_class(target_day, class_id)

        hour = int(target_time[0:2])
        minute = int(target_time[2:4])
        cb(f'class booked for {email}: {class_name} {hour}:{minute}')

    @staticmethod
    def __get_class_to_book(classes: list[dict], target_time: str, class_name: str):
        if not classes or len(classes) == 0:
            raise BoxClosed(MESSAGE_BOX_IS_CLOSED)

        classes = list(filter(lambda _class: target_time in _class["timeid"], classes))
        _class = list(filter(lambda _class: class_name in _class["className"], classes))
        if len(_class) == 0:
            raise NoBookingGoal(
                f"No class with the text `{class_name}` in its name at time `{target_time}`"
            )
        return _class[0]["id"]

    @staticmethod
    def __load_schedules_configuration():
        script_dir = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(script_dir, 'schedule.json')

        with open(file_path, 'r') as f:
             return json.load(f)
