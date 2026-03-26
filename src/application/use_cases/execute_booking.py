from domain.exceptions import (
    BookingFailed,
    MESSAGE_BOX_IS_CLOSED,
    MESSAGE_GYM_CLASS_NOT_FOUND,
    UserNotFound,
)
from domain.models import BookingGoal
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

    def execute(self, user_id: int, booking_goal: BookingGoal) -> None:
        user = self._user_repo.get_user(user_id)
        if user is None:
            raise UserNotFound(f"User {user_id} not found")

        client = self._gym_client_factory.create(user)
        classes = client.get_classes(booking_goal.class_start)

        if not classes:
            raise BookingFailed(MESSAGE_BOX_IS_CLOSED)

        matched = next(
            (
                c
                for c in classes
                if c.class_start == booking_goal.class_start
                and booking_goal.class_name in c.name
            ),
            None,
        )
        if matched is None:
            raise BookingFailed(
                f"{MESSAGE_GYM_CLASS_NOT_FOUND}: '{booking_goal.class_name}' at "
                f"{booking_goal.class_start.strftime('%H:%M')} on "
                f"{booking_goal.class_start.date()}"
            )

        client.book_class(matched)

        self._booking_repo.remove_booking_goal(user_id, booking_goal)

        msg = (
            f"class booked for {user.email}: {booking_goal.class_name} "
            f"{booking_goal.class_start.strftime('%H:%M')}"
        )
        self._user_notifier.notify_user(user_id, msg)
        self._group_notifier.notify_group(msg)
