from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from box_data import box_id, box_name, days_in_advance
from client import AimHarderClient
from exceptions import (
    NoBookingGoal,
    BoxClosed,
    MESSAGE_BOX_IS_CLOSED,
)
from src.repository import JsonRepository


class BookingScheduler:
    def __init__(self, repository: JsonRepository):
        self.__scheduler = BackgroundScheduler()
        self.__repository = repository

    def start(self):
        self.__scheduler.start()

    def schedule_unique_execution(self, date: datetime, class_name, user_id, cb):
        job = self.__scheduler.add_job(
            self.__execution,
            trigger=DateTrigger(run_date=date - timedelta(days=days_in_advance)),
            kwargs=dict(
                user_id=user_id,
                target_time=date.strftime('%H%M'),
                class_name=class_name,
                cb=cb
            )
        )

        self.__repository.add_booking_to_user(user_id, {
            'datetime': date.strftime('%d-%m-%Y %H:%M'),
            'name': class_name,
            'job_id': job.id
        })

    def remove_unique_execution(self, job_id):
        self.__scheduler.remove_job(job_id)

    def __execution(self, user_id, target_time, class_name, cb):
        user = self.__repository.get_user_schedule_configuration(user_id)['user']
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
