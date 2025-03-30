import copy
import json
import os
from datetime import datetime, timedelta

from src.box_data import days_in_advance


class JsonRepository:

    def __init__(self):
        self.__data = self.load()

    @property
    def __file_path(self):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(script_dir, 'schedule.json')

    def get_user_schedule_configuration(self, user_id):
        return copy.deepcopy(self.__find_user_schedule_configuration(user_id))

    def add_booking_to_user(self, user_id, booking_goal):
        user_schedule_data = self.__find_user_schedule_configuration(user_id)
        already_registered_booking = self.__find_booking_schedule(user_id, booking_goal)
        already_registered_booking_datetime = datetime.strptime(already_registered_booking['datetime'], '%d-%m-%Y %H:%M')
        if already_registered_booking and  already_registered_booking_datetime < (datetime.now() + timedelta(days=days_in_advance)):
            self.delete_booking_from_user(user_id, already_registered_booking['job_id'])
            return

        if already_registered_booking is not None:
            already_registered_booking.update({'job_id': booking_goal['job_id']})
        else:
            user_schedule_data['bookingGoals'].append(booking_goal)

        self.__save()

    def load(self):
        with open(self.__file_path, 'r') as f:
            return json.load(f)

    def __save(self):
        json_dump = json.dumps(self.__data, indent=4)
        with open(self.__file_path, 'w', encoding='utf-8') as file:
            file.write(json_dump)

    def __find_user_schedule_configuration(self, user_id):
        return next((data for data in self.__data if data['user']['id'] == user_id), None)

    def __find_booking_schedule(self, user_id, new_booking_goal):
        user_booking_data = self.__find_user_schedule_configuration(user_id)['bookingGoals']
        return next((booking_goal for booking_goal in user_booking_data if
                     self.__booking_goals_are_the_same(booking_goal, new_booking_goal)), None)

    @staticmethod
    def __booking_goals_are_the_same(booking_goal_1, booking_goal_2):
        return (booking_goal_1["name"] == booking_goal_2["name"] and
                booking_goal_1["datetime"] == booking_goal_2["datetime"])

    def delete_booking_from_user(self, user_id, job_id):
        user_schedule_configuration = self.__find_user_schedule_configuration(user_id)
        user_booking_goals = user_schedule_configuration['bookingGoals']
        user_schedule_configuration['bookingGoals'] = [booking_goal for booking_goal in
                                                       user_booking_goals if
                                                       booking_goal['job_id'] != job_id]
        self.__save()

    def find_job_id(self, user_id, class_date: datetime, class_name):
        user_schedule_configuration = self.__find_user_schedule_configuration(user_id)
        user_booking_goals = user_schedule_configuration['bookingGoals']
        return next((
            booking_goal['job_id'] for booking_goal in
            user_booking_goals if
            booking_goal['name'] != class_name and datetime.strptime(booking_goal['datetime'], '%d-%m-%Y %H:%M') == class_date
        ), None)
