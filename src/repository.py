import copy
import json
import os


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
        if self.__is_booking_already_scheduled(user_id, booking_goal):
            return

        user_schedule_data = self.__find_user_schedule_configuration(user_id)
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
        return next(data for data in self.__data if data['user']['id'] == user_id)

    def __is_booking_already_scheduled(self, user_id, new_booking_goal):
        user_booking_data = self.__find_user_schedule_configuration(user_id)['bookingGoals']
        return next((booking_goal for booking_goal in user_booking_data if
                    self.__booking_goals_are_the_same(booking_goal, new_booking_goal)), None) is not None

    @staticmethod
    def __booking_goals_are_the_same(booking_goal_1, booking_goal_2):
        return (booking_goal_1["name"] == booking_goal_2["name"] and
                booking_goal_1["datetime"] == booking_goal_2["datetime"])

