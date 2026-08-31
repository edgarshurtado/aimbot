import copy

from domain.models import BookingGoal, BookingSchedule, User
from domain.ports.booking_repository import IBookingRepository
from domain.ports.user_repository import IUserRepository


class InMemoryUserRepository(IUserRepository):
    def __init__(self, users: list[User] | None = None) -> None:
        self._users = {u.id: u for u in (users or [])}

    def get_user(self, user_id: int) -> User | None:
        user = self._users.get(user_id)
        if user is None:
            return None
        # A deep copy, so a caller holding the result — or mutating one of its
        # BookingGoal entries — cannot reach into the store. dataclasses.replace
        # is shallow and would share the BookingSchedule and its goals with the
        # store; JsonRepository promises a real deep copy, so this fake must too.
        return copy.deepcopy(user)

    def get_all_users(self) -> list[User]:
        return [self.get_user(user_id) for user_id in self._users]


class InMemoryBookingRepository(IBookingRepository):
    def __init__(self) -> None:
        self._bookings: dict[int, list[BookingGoal]] = {}

    def get_user_bookings(self, user_id: int) -> BookingSchedule:
        return BookingSchedule(self._bookings.get(user_id, []))

    def add_booking_goal(self, user_id: int, goal: BookingGoal) -> None:
        self._bookings.setdefault(user_id, []).append(goal)

    def remove_booking_goal(self, user_id: int, goal: BookingGoal) -> None:
        self._bookings.get(user_id, []).remove(goal)
