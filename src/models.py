from typing import List


class BookingGoal:
    def __init__(self, datetime, name, job_id):
        self.datetime = datetime
        self.name = name
        self.job_id = job_id

    @staticmethod
    def from_dict(data) -> 'BookingGoal':
        datetime = data["datetime"]
        name = data["name"]
        job_id = data["job_id"]
        return BookingGoal(datetime, name, job_id)

class User:
    def __init__(self, user_id, email, password, booking_goals: List[BookingGoal] = None):
        self.id = user_id
        self.email = email
        self.password = password
        self.booking_goals = booking_goals if booking_goals is not None else []