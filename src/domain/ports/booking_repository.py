from abc import ABC, abstractmethod
from domain.models import BookingGoal
from error_handling import Result


class IBookingRepository(ABC):
    @abstractmethod
    def get_user_bookings(self, user_id: int) -> list[BookingGoal]: ...

    @abstractmethod
    def add_booking_goal(self, user_id: int, goal: BookingGoal) -> Result: ...

    @abstractmethod
    def remove_booking_goal(self, user_id: int, goal: BookingGoal) -> None: ...
