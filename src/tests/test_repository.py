import uuid
from datetime import datetime, timedelta
from unittest import TestCase

from src.repository import JsonRepository

mock_json_load = [
    {
        "user": {
            "email": "some-email@gmail.com",
            "password": "password",
            "id": 66666666
        },
        "bookingGoals": [],
        "recurrentBookingGoals": {}
    }
]

class TestRepository(TestCase):
    def setUp(self):
        self.repository = JsonRepository('test_schedule.json')
        self.test_user_id = 66666666

    def tearDown(self):
        self.repository.delete_all_user_booking_goals(self.test_user_id)

    def test_add_booking_to_user(self):
        job_id = str(uuid.uuid4())
        datetime_str = (datetime.now() + timedelta(days=1)).strftime('%d-%m-%Y %H:%M')

        self.repository.add_booking_to_user(
            user_id=self.test_user_id,
            booking_goal={
                "datetime": datetime_str,
                "name": "OPEN",
                'job_id': job_id
            }
        )
        user_schedule = self.repository.get_user_schedule_configuration(self.test_user_id)
        added_booking_goal = next(bookingGoal for bookingGoal in user_schedule['bookingGoals'] if bookingGoal['job_id'] == job_id)
        self.assertEqual(added_booking_goal["name"], "OPEN")
        self.assertEqual(added_booking_goal["datetime"], datetime_str)
