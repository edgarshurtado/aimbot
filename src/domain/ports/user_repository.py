from abc import ABC, abstractmethod
from domain.models import User


class IUserRepository(ABC):
    @abstractmethod
    def get_user(self, user_id: int) -> User | None:
        """The user, whose booking_goals are a BookingSchedule: soonest first.

        The ordering is part of the contract, not an implementation detail:
        callers address a member's goals by position (the number /schedule
        prints is the number /remove consumes), so two implementations ordering
        differently would make the same number mean different goals. The type
        enforces it — an implementation cannot get this wrong.
        """

    @abstractmethod
    def get_all_users(self) -> list[User]:
        """Every user, each with the BookingSchedule described in ``get_user``."""
