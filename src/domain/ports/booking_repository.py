from abc import ABC, abstractmethod
from domain.models import BookingGoal, BookingSchedule


class IBookingRepository(ABC):
    @abstractmethod
    def get_user_bookings(self, user_id: int) -> BookingSchedule:
        """The user's booking goals, ordered by class start, soonest first.

        Since trigger time is a fixed interval before the class starts, this is
        also the order the goals will be attempted in. The return type is the
        guarantee: a BookingSchedule sorts on construction and has no mutators,
        so no implementation can hand back an unordered collection.
        """

    @abstractmethod
    def add_booking_goal(self, user_id: int, goal: BookingGoal) -> None: ...

    @abstractmethod
    def remove_booking_goal(self, user_id: int, goal: BookingGoal) -> None: ...
