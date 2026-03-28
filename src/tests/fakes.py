from domain.models import BookingGoal, User
from domain.ports.booking_repository import IBookingRepository
from domain.ports.user_repository import IUserRepository


class InMemoryUserRepository(IUserRepository):
    def __init__(self, users: list[User] | None = None) -> None:
        self._users = {u.id: u for u in (users or [])}

    def get_user(self, user_id: int) -> User | None:
        return self._users.get(user_id)

    def get_all_users(self) -> list[User]:
        return list(self._users.values())


class InMemoryBookingRepository(IBookingRepository):
    def __init__(self) -> None:
        self._bookings: dict[int, list[BookingGoal]] = {}

    def get_user_bookings(self, user_id: int) -> list[BookingGoal]:
        return list(self._bookings.get(user_id, []))

    def add_booking_goal(self, user_id: int, goal: BookingGoal) -> None:
        self._bookings.setdefault(user_id, []).append(goal)

    def remove_booking_goal(self, user_id: int, goal: BookingGoal) -> None:
        self._bookings.get(user_id, []).remove(goal)
