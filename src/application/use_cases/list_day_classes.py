from datetime import datetime

from domain.exceptions import UserNotFound
from domain.models import GymClass
from domain.ports.gym_client import IGymClientFactory
from domain.ports.user_repository import IUserRepository


class ListDayClassesUseCase:
    """Reads a day's published Timetable so a member can pick a class that exists.

    The Timetable is published long before the day's Booking Window opens, so this
    answers for days that are not yet bookable — which is exactly when a member is
    choosing.
    """

    def __init__(
        self,
        user_repo: IUserRepository,
        gym_client_factory: IGymClientFactory,
    ) -> None:
        self._user_repo = user_repo
        self._gym_client_factory = gym_client_factory

    def execute(self, user_id: int, day: datetime) -> list[GymClass]:
        user = self._user_repo.get_user(user_id)
        if user is None:
            raise UserNotFound(f"User {user_id} not found")

        client = self._gym_client_factory.create(user)
        classes = client.get_classes(day)
        # Sorted explicitly: the platform's ordering is not a documented guarantee
        # and the keyboard the member sees must be stable.
        return sorted(classes, key=lambda c: (c.class_start, c.name))
