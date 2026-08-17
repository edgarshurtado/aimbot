from dataclasses import replace

from domain.models import BookingGoal, User
from domain.ports.booking_repository import IBookingRepository
from domain.ports.user_repository import IUserRepository


def _soonest_first(goals: list[BookingGoal]) -> list[BookingGoal]:
    """The ordering both repository ports promise. See IBookingRepository."""
    return sorted(goals, key=lambda goal: goal.class_start)


class InMemoryUserRepository(IUserRepository):
    def __init__(self, users: list[User] | None = None) -> None:
        self._users = {u.id: u for u in (users or [])}

    def get_user(self, user_id: int) -> User | None:
        user = self._users.get(user_id)
        if user is None:
            return None
        return replace(user, booking_goals=_soonest_first(user.booking_goals))

    def get_all_users(self) -> list[User]:
        return [self.get_user(user_id) for user_id in self._users]


class InMemoryBookingRepository(IBookingRepository):
    def __init__(self) -> None:
        self._bookings: dict[int, list[BookingGoal]] = {}

    def get_user_bookings(self, user_id: int) -> list[BookingGoal]:
        return _soonest_first(self._bookings.get(user_id, []))

    def add_booking_goal(self, user_id: int, goal: BookingGoal) -> None:
        self._bookings.setdefault(user_id, []).append(goal)

    def remove_booking_goal(self, user_id: int, goal: BookingGoal) -> None:
        self._bookings.get(user_id, []).remove(goal)
