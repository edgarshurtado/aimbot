from abc import ABC, abstractmethod
from domain.models import BookingGoal, BookingSchedule


class IBookingRepository(ABC):
    @abstractmethod
    def get_user_bookings(self, user_id: int) -> BookingSchedule:

    @abstractmethod
    def add_booking_goal(self, user_id: int, goal: BookingGoal) -> None: ...

    @abstractmethod
    def remove_booking_goal(self, user_id: int, goal: BookingGoal) -> None: ...
