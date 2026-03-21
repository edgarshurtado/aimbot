from datetime import datetime

from domain.exceptions import BoxClosed, NoBookingGoal, MESSAGE_BOX_IS_CLOSED
from domain.ports.booking_repository import IBookingRepository
from domain.ports.gym_client import IGymClientFactory
from domain.ports.notifier import IGroupNotifier, IUserNotifier
from domain.ports.user_repository import IUserRepository


class ExecuteBookingUseCase:
    def __init__(
        self,
        user_repo: IUserRepository,
        booking_repo: IBookingRepository,
        gym_client_factory: IGymClientFactory,
        user_notifier: IUserNotifier,
        group_notifier: IGroupNotifier,
    ) -> None:
        self._user_repo = user_repo
        self._booking_repo = booking_repo
        self._gym_client_factory = gym_client_factory
        self._user_notifier = user_notifier
        self._group_notifier = group_notifier

    def execute(self, user_id: int, booking_date: datetime, class_name: str) -> None:
        user = self._user_repo.get_user(user_id)
        if user is None:
            raise ValueError(f"User {user_id} not found")

        client = self._gym_client_factory.create(user.email, user.password)
        classes = client.get_classes(booking_date)

        if not classes:
            raise BoxClosed(MESSAGE_BOX_IS_CLOSED)

        matched = next(
            (c for c in classes if c.start_time == booking_date.time() and class_name in c.name),
            None,
        )
        if matched is None:
            raise NoBookingGoal(
                f"No class '{class_name}' at {booking_date.strftime('%H:%M')} on {booking_date.date()}"
            )

        client.book_class(booking_date, matched.id)

        goal = self._booking_repo.find_booking_goal(user_id, booking_date, class_name)
        if goal is not None:
            self._booking_repo.remove_booking_goal(user_id, booking_date, class_name)

        msg = (
            f"class booked for {user.email}: {class_name} "
            f"{booking_date.strftime('%H:%M')}"
        )
        self._user_notifier.notify_user(user_id, msg)
        self._group_notifier.notify_group(msg)
